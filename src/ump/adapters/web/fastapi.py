# ump/adapters/web/fastapi.py
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ump.core.interfaces.http_client import HttpClientPort
from ump.core.interfaces.process_id_validator import ProcessIdValidatorPort
from ump.core.interfaces.processes import ProcessesPort
from ump.core.interfaces.providers import ProvidersPort
from ump.core.exceptions import OGCProcessException
from ump.core.managers.process_manager import ProcessManager

# Note: this a driver adapter, so it depends on the core interface (ProcessesPort)
# but the core does not depend on this adapter
# it does not need to implement a port/interface itself
# it just uses the interface of the core (ProcessesPort)
def create_app(
    provider_config_service: ProvidersPort,
    http_client: HttpClientPort,
    process_id_validator: ProcessIdValidatorPort
):
    # must not be injected directly, because it needs to be created in the lifespan
    process_port: ProcessesPort | None = None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal process_port

        async with http_client as client:
            process_port = ProcessManager(
                provider_config_service, client,
                process_id_validator=process_id_validator
            )
            app.state.process_port = process_port
            yield
    
    app = FastAPI(lifespan=lifespan)

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
            }
        )

    @app.get("/processes")
    async def get_all_processes():
        return await app.state.process_port.get_all_processes()

    return app