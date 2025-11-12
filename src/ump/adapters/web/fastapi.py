# ump/adapters/web/fastapi.py
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from ump.core.exceptions import OGCProcessException
from ump.core.interfaces.http_client import HttpClientPort
from ump.core.interfaces.process_id_validator import ProcessIdValidatorPort
from ump.core.interfaces.processes import ProcessesPort
from ump.core.interfaces.providers import ProvidersPort
from ump.core.interfaces.site_info import SiteInfoPort
from ump.core.managers.job_manager import JobManager
from ump.core.managers.process_manager import ProcessManager
from ump.core.models.execute_request import ExecuteRequest, InlineOrRef
from ump.core.models.job import JobList, JobStatusInfo
from ump.core.models.process import Process, ProcessList
from ump.core.settings import app_settings


# Note: this a driver adapter, so it depends on the core interface (ProcessesPort)
# but the core does not depend on this adapter
# it does not need to implement a port/interface itself
# it just uses the interface of the core (ProcessesPort)
def create_app(
    process_manager_factory: Callable[[HttpClientPort], ProcessManager],
    http_client: HttpClientPort,
    job_manager_factory: Callable[[HttpClientPort, ProcessManager], JobManager],
    site_info: SiteInfoPort | None = None,
):
    """Create the FastAPI app.

    Adapters and concrete infrastructure (logging, repositories, providers) are
    assembled outside and passed as factories. This keeps the web adapter focused
    purely on HTTP concerns and lifecycle orchestration.
    """
    process_port: ProcessesPort | None = None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal process_port
        async with http_client as client:
            process_port = process_manager_factory(client)
            job_manager = job_manager_factory(
                client, process_port
            )  # already wired externally

            # Safe attach: ProcessManager defines attach_job_manager; guard via hasattr
            if hasattr(process_port, "attach_job_manager"):
                getattr(process_port, "attach_job_manager")(job_manager)
            app.state.process_port = process_port
            try:
                yield
            finally:
                if hasattr(job_manager, "shutdown"):
                    await job_manager.shutdown()

    app = FastAPI(lifespan=lifespan)

    # Helper: create a versioned sub-app that mounts the same handlers but with its own openapi URL
    def create_versioned_app(version: str):
        ver_prefix = f"v{version}"
        # sub-app with its own OpenAPI document exposed under the version prefix
        sub = FastAPI(
            title=f"UMP API v{version}",
            # use relative openapi/docs paths; they will be available under the mount prefix
            openapi_url="/openapi.json",
            docs_url="/docs",
            redoc_url="/redoc",
        )

        # Reuse the same static/templates for sub-apps by mounting the same directories
        if adapter_static.exists():
            sub.mount(
                "/static",
                StaticFiles(directory=str(adapter_static)),
                name=f"static-{version}",
            )

        # add routes similar to parent but using sub.state for process_port resolution
        @sub.get(
            "/processes", response_model=ProcessList, response_model_exclude_none=True
        )
        async def get_all_processes_sub():
            # sub-app will share state.process_port from parent app.state
            process_list = await app.state.process_port.get_all_processes()
            return process_list

        @sub.get(
            "/processes/{process_id}",
            response_model=Process,
            response_model_exclude_none=True,
        )
        async def get_process_sub(process_id: str):
            process = await app.state.process_port.get_process(process_id)
            return process

        @sub.get("/jobs", response_model=JobList, response_model_exclude_none=True)
        async def list_jobs_sub():
            # Access job repository via process_port
            repo = getattr(app.state.process_port, "job_repository", None)
            if repo is None:
                return JobList(jobs=[], links=[])
            jobs = await repo.list()
            status_infos = [j.status_info for j in jobs if j.status_info]
            # Minimal self link list for collection
            collection_links = []
            return JobList(jobs=status_infos, links=collection_links)

        @sub.get(
            "/jobs/{job_id}",
            response_model=JobStatusInfo,
            response_model_exclude_none=True,
        )
        async def get_job_sub(job_id: str):
            repo = getattr(app.state.process_port, "job_repository", None)
            if repo is None:
                return JSONResponse(
                    status_code=404, content={"detail": "Jobs not supported"}
                )
            job = await repo.get(job_id)
            if not job or not job.status_info:
                return JSONResponse(
                    status_code=404, content={"detail": "Job not found"}
                )
            return job.status_info

        return sub, ver_prefix

    # Serve static files and templates from the adapter package itself
    adapter_root = Path(__file__).parent
    adapter_static = adapter_root / "static"
    adapter_templates = adapter_root / "templates"

    if adapter_static.exists():
        app.mount("/static", StaticFiles(directory=str(adapter_static)), name="static")

    templates = Jinja2Templates(directory=str(adapter_templates))

    # Mount versioned sub-apps for each supported API version
    for ver in getattr(app_settings, "UMP_SUPPORTED_API_VERSIONS", ["1.0"]):
        sub_app, ver_prefix = create_versioned_app(ver)
        # mount under e.g. /v1.0
        mount_path = f"/v{ver}"
        app.mount(mount_path, sub_app)

    # Dedicated route for the landing CSS. This is a robust fallback for environments
    # where StaticFiles mounting might not be available (packaged apps, different cwd).
    @app.get("/landing.css", name="landing_css")
    async def landing_css():
        css_path = Path(__file__).parent / "static" / "landing.css"
        if css_path.exists():
            return FileResponse(str(css_path), media_type="text/css")
        return JSONResponse(status_code=404, content={})

    # Landing page route (optional) - uses site_info adapter if provided
    @app.get("/", response_class=HTMLResponse)
    async def landing(request: Request):
        # Content negotiation: query param 'f' or Accept header
        f = request.query_params.get("f")
        accept = request.headers.get("accept", "")

        api = (
            site_info.get_site_info()
            if site_info is not None
            else {
                "title": "Urban Model Platform",
                "description": "API available at /processes",
                "routes": [
                    {"path": "/processes", "description": "List available processes"}
                ],
                "contact": "",
            }
        )

        # JSON response when requested
        if f == "json" or ("application/json" in accept and f != "html"):
            return JSONResponse(api)

        # Build table rows
        links = api.get("routes", [])
        table_rows = "".join(
            f"<tr><td><a href='{r['path']}'>{r['path']}</a></td><td>{r.get('description', '')}</td></tr>"
            for r in links
        )

        contact = api.get("contact") or {}
        contact_line = " | ".join(
            filter(
                None,
                [
                    f"<a href='{contact.get('url')}'>{contact.get('name')}</a>"
                    if isinstance(contact, dict) and contact.get("url")
                    else None,
                    f"<a href='mailto:{contact.get('email')}'>{contact.get('email')}</a>"
                    if isinstance(contact, dict) and contact.get("email")
                    else None,
                ],
            )
        )

        # Adapter-local style
        css_href = "/static/style.css"

        # Also include discovered supported versions for the template
        supported_versions = getattr(
            app_settings, "UMP_SUPPORTED_API_VERSIONS", ["1.0"]
        )

        context = {
            "request": request,
            "title": api.get("title"),
            "version": ", ".join(supported_versions),
            "description": api.get("description"),
            "contact_line": contact_line,
            "license_line": "",
            "terms_of_service": "",
            "powered_by": "<a href='https://github.com/citysciencelab/urban-model-platform'>urban-model-platform</a>",
            "css": css_href,
            "table_rows": table_rows,
            "supported_versions": supported_versions,
        }

        return templates.TemplateResponse("template.html", context)

    # Exception handler for OGC Process exceptions
    @app.exception_handler(OGCProcessException)
    async def ogc_exception_handler(request: Request, exc: OGCProcessException):
        return JSONResponse(
            status_code=exc.response.status,
            content={
                "type": exc.response.type,
                "title": exc.response.title,
                "status": exc.response.status,
                "detail": exc.response.detail,
                "instance": exc.response.instance,
            },
        )

    @app.get(
        "/processes",
        response_model=ProcessList,
        response_model_exclude_none=True,
        response_model_by_alias=True,
    )
    async def get_all_processes():
        process_list = await app.state.process_port.get_all_processes()
        return process_list

    @app.get(
        "/processes/{process_id}",
        response_model=Process,
        response_model_exclude_none=True,
        response_model_by_alias=True,
    )
    async def get_process(process_id: str):
        process = await app.state.process_port.get_process(process_id)
        return process

    @app.get("/jobs", response_model=JobList, response_model_exclude_none=True)
    async def list_jobs():
        repo = getattr(app.state.process_port, "job_repository", None)
        if repo is None:
            return JobList(jobs=[], links=[])
        jobs = await repo.list()
        status_infos = [j.status_info for j in jobs if j.status_info]
        return JobList(jobs=status_infos, links=[])

    @app.get(
        "/jobs/{job_id}", response_model=JobStatusInfo, response_model_exclude_none=True
    )
    async def get_job(job_id: str):
        repo = getattr(app.state.process_port, "job_repository", None)
        if repo is None:
            return JSONResponse(
                status_code=404, content={"detail": "Jobs not supported"}
            )
        job = await repo.get(job_id)
        if not job or not job.status_info:
            return JSONResponse(status_code=404, content={"detail": "Job not found"})
        return job.status_info

    @app.post("/processes/{process_id}/execution")
    async def execute_process(request: Request, process_id: str):
        # Parse and validate execute request body against ExecuteRequest model.
        try:
            raw = await request.json()
        except Exception:
            raw = {}

        try:
            exec_req = ExecuteRequest.from_raw(raw)
        except ValidationError as ve:
            return JSONResponse(
                status_code=400,
                content={
                    "type": "about:blank",
                    "title": "Invalid Execute Request",
                    "detail": ve.errors(),
                },
            )

        # Collect headers of interest (Prefer) and forward the rest if needed
        headers = {}
        prefer = request.headers.get("prefer") or request.headers.get("Prefer")
        if prefer:
            headers["Prefer"] = prefer

        provider_payload = exec_req.as_provider_payload()
        # We pass only normalized input values (provider_payload['inputs']) to JobManager for storage.
        resp = await app.state.process_port.execute_process(
            process_id, provider_payload.get("inputs", {}), headers
        )

        # need to return location header to client when async execute
        # locate job id from provider response header
        # translate into this servers url
        # return to client

        # If the backend returned structured dict with status/headers/body, map to response
        if isinstance(resp, dict) and "status" in resp:
            status = resp.get("status") or 200
            content = resp.get("body") or {}
            location = None
            
            if isinstance(resp.get("headers"), dict):
                location = resp["headers"].get("Location")
            
            safe_content = jsonable_encoder(content)
            response = JSONResponse(status_code=status, content=safe_content)
            
            if location:
                response.headers["Location"] = location
            return response

        # Otherwise return generic JSON
        return JSONResponse(status_code=200, content=resp or {})

    return app
