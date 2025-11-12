"""JobManager: orchestrates local job creation and remote execution forwarding.

Responsibilities (Step 1):
1. Create local job with accepted snapshot.
2. Forward execute request to remote provider.
3. Extract initial statusInfo (direct body or via Location polling once).
4. Persist job & status history.
5. Schedule background polling until terminal state.
6. Return 201 Created + Location + statusInfo body.
"""

from __future__ import annotations

import uuid
import asyncio
from typing import Any, Dict, Optional, Set
from datetime import datetime, timezone
from urllib.parse import urljoin

from ump.core.interfaces.http_client import HttpClientPort
from ump.core.interfaces.process_id_validator import ProcessIdValidatorPort
from ump.core.interfaces.providers import ProvidersPort
from ump.core.interfaces.job_repository import JobRepositoryPort
from ump.core.models.job import Job, JobStatusInfo, StatusCode
from ump.core.exceptions import OGCProcessException
from ump.core.models.ogcp_exception import OGCExceptionResponse
from ump.core.settings import logger, app_settings


REQUIRED_STATUS_FIELDS = {"jobID", "status", "type"}


class JobManager:
    def __init__(
        self,
        providers: ProvidersPort,
        http_client: HttpClientPort,
        process_id_validator: ProcessIdValidatorPort,
        job_repo: JobRepositoryPort,
    ) -> None:
        self._providers = providers
        self._http = http_client
        self._validator = process_id_validator
        self._repo = job_repo
        self._poll_interval = getattr(app_settings, "UMP_REMOTE_JOB_STATUS_REQUEST_INTERVAL", 5)
        self._poll_tasks: Set[asyncio.Task] = set()
        self._shutdown = False

    async def create_and_forward(
        self,
        process_id: str,
        execute_payload: Optional[Dict[str, Any]],
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        """Primary orchestration entrypoint.

        `execute_payload` is the full normalized ExecuteRequest provider payload.
        We persist only inputs (inline small) locally but forward the complete
        structure downstream, preserving outputs/response/subscriber options.
        On provider error responses that are NOT statusInfo JSON we propagate
        the upstream body (JSON or text) and status code to the caller instead
        of collapsing to a generic 'missing statusInfo'.
        """
        logger.info(f"[job:create] incoming execute request for process_id={process_id} headers_prefer={headers.get('Prefer') or headers.get('prefer')}")
        provider_prefix, raw_id = await self._resolve_provider(process_id)
        provider = self._providers.get_provider(provider_prefix)
        logger.debug(f"[job:create] resolved provider prefix={provider_prefix} raw_id={raw_id} provider_url={getattr(provider, 'url', None)}")

        inputs = execute_payload.get("inputs") if isinstance(execute_payload, dict) else None
        if inputs:
            logger.debug(f"[job:create] inputs keys={list(inputs.keys())[:8]} total_keys={len(inputs.keys())}")
        job = await self._init_job(process_id, provider_prefix, inputs)
        logger.debug(f"[job:create] initialized local job id={job.id} inline_inputs={'yes' if job.inputs else 'no'}")
        accepted_si = await self._persist_accepted(job, process_id)
        logger.debug(f"[job:create] persisted accepted snapshot job_id={job.id} created={accepted_si.created}")

        prefer = headers.get("Prefer") or headers.get("prefer")
        forward_headers = {"Prefer": prefer} if prefer else {}

        exec_url = str(provider.url).rstrip("/") + f"/processes/{raw_id}/execution"
        logger.debug(f"[job:forward] forwarding to exec_url={exec_url} prefer={prefer} payload_keys={list(execute_payload.keys()) if isinstance(execute_payload, dict) else 'n/a'}")

        provider_resp = await self._safe_forward(job, exec_url, execute_payload or {}, forward_headers)

        if provider_resp is None:
            failed_job = await self._repo.get(job.id)
            logger.debug(f"[job:forward] upstream forward failed immediately job_id={job.id} returning failed status")
            return self._response(job.id, failed_job.status_info if failed_job and failed_job.status_info else None)

        # If upstream returned non-statusInfo body with error code (>=400), propagate directly
        upstream_status = provider_resp.get("status")
        upstream_body = provider_resp.get("body")
        logger.debug(f"[job:forward] upstream response status={upstream_status} has_location={bool(provider_resp.get('headers', {}).get('Location'))} body_type={type(upstream_body).__name__}")
        if upstream_status and upstream_status >= 400:
            si = self._extract_status_info(upstream_body)
            if not si:
                # mark local job failed but return original upstream error body
                await self._repo.mark_failed(job.id, reason=f"Upstream {upstream_status}")
                logger.debug(f"[job:error-propagate] marking job failed job_id={job.id} upstream_status={upstream_status} returning raw upstream body")
                return {
                    "status": upstream_status,
                    "headers": {"Location": f"/jobs/{job.id}"},
                    "body": upstream_body if isinstance(upstream_body, (dict, list)) else {"error": str(upstream_body)}
                }

        status_info, remote_status_url, remote_job_id, diagnostic = await self._derive_status_info(
            job, process_id, provider, provider_resp, accepted_si
        )
        logger.debug(
            f"[job:derive] job_id={job.id} derived_status={status_info.status if status_info else None} remote_status_url={remote_status_url} remote_job_id={remote_job_id} diagnostic_set={bool(diagnostic)}"
        )

        await self._finalize_job(job, status_info, remote_status_url, remote_job_id, diagnostic)
        return self._response(job.id, status_info)

    # ----------------- Helper methods -----------------
    async def _init_job(
        self, process_id: str, provider_prefix: str, inputs: Optional[Dict[str, Any]]
    ) -> Job:
        # Local UUID creation: we intentionally decouple local job identity from any remote job id.
        # This guards against collisions across providers and allows stable user-facing references
        # even if upstream retries or reassigns a different remote identifier.
        job_id = str(uuid.uuid4())
        job = Job(
            id=job_id,
            process_id=process_id,
            provider=provider_prefix,
            status=str(StatusCode.accepted),
            inputs=inputs if inputs and self._is_inline_small(inputs) else None,
            inputs_storage="inline" if inputs and self._is_inline_small(inputs) else "object" if inputs else "inline",
        )
        return job

    async def _persist_accepted(self, job: Job, process_id: str) -> JobStatusInfo:
        accepted_si = JobStatusInfo(
            jobID=job.id,
            status=StatusCode.accepted,
            type="process",
            processID=process_id,
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc),
            message=None,
            progress=0,
        )
        job.apply_status_info(accepted_si)
        await self._repo.create(job)
        await self._repo.append_status(job.id, accepted_si)
        return accepted_si

    async def _safe_forward(
        self, job: Job, exec_url: str, payload: Dict[str, Any], headers: Dict[str, str]
    ) -> Optional[Dict[str, Any]]:
        try:
            logger.debug(f"[job:forward] POST exec_url={exec_url} job_id={job.id} headers={list(headers.keys())} payload_size={len(str(payload))}")
            resp = await self._http.post(exec_url, json=payload, headers=headers)
            logger.debug(f"[job:forward] POST completed job_id={job.id} status={resp.get('status')} keys={list(resp.keys())}")
            return resp
        except OGCProcessException as exc:
            await self._repo.mark_failed(
                job.id, reason=exc.response.title, diagnostic=exc.response.detail
            )
            logger.warning(f"[job:forward] OGCProcessException job_id={job.id} title={exc.response.title}")
        except Exception as exc:
            await self._repo.mark_failed(
                job.id, reason="Upstream Error", diagnostic=str(exc)
            )
            logger.error(f"[job:forward] unexpected exception job_id={job.id} error={exc}")
        return None

    async def _derive_status_info(
        self,
        job: Job,
        process_id: str,
        provider: Any,
        provider_resp: Dict[str, Any],
        accepted_si: JobStatusInfo,
    ) -> tuple[JobStatusInfo, Optional[str], Optional[str], Optional[str]]:
        provider_headers = provider_resp.get("headers", {})
        provider_body = provider_resp.get("body")
        provider_status = provider_resp.get("status")

        status_info = self._extract_status_info(provider_body)
        remote_status_url: Optional[str] = None
        remote_job_id: Optional[str] = None
        diagnostic: Optional[str] = None

        if not status_info and provider_headers.get("Location"):
            location = provider_headers["Location"]
            resolved = self._resolve_location(str(provider.url), location)
            remote_status_url = resolved
            try:
                logger.debug(f"[job:derive] following provider Location job_id={job.id} location={location} resolved={resolved}")
                follow_resp = await self._http.get(resolved)
                status_info = self._extract_status_info(follow_resp)
            except Exception as follow_err:
                logger.warning(
                    f"Failed to follow provider Location {location}: {follow_err}"
                )

        if not status_info:
            logger.debug(f"[job:derive] missing statusInfo, marking failed job_id={job.id}")
            status_info = JobStatusInfo(
                jobID=job.id,
                status=StatusCode.failed,
                type="process",
                processID=process_id,
                message="Provider response missing statusInfo",
                updated=datetime.now(timezone.utc),
                created=accepted_si.created,
                progress=None,
            )
            diagnostic = f"provider_status={provider_status} body_type={type(provider_body).__name__}"
        else:
            # Remote job id capture: if provider supplies a different jobID we store it separately
            # (remote_job_id) and normalize the user-facing statusInfo.jobID back to our local UUID.
            # This maintains OGC statusInfo schema while keeping our route stable.
            if status_info.jobID and status_info.jobID != job.id:
                remote_job_id = status_info.jobID
                status_info.jobID = job.id
                logger.debug(f"[job:derive] captured remote_job_id={remote_job_id} mapped_to_local job_id={job.id}")
            status_info.processID = process_id

        return status_info, remote_status_url, remote_job_id, diagnostic

    async def _finalize_job(
        self,
        job: Job,
        status_info: JobStatusInfo,
        remote_status_url: Optional[str],
        remote_job_id: Optional[str],
        diagnostic: Optional[str],
    ) -> None:
        if remote_status_url:
            job.remote_status_url = remote_status_url
        if remote_job_id:
            job.remote_job_id = remote_job_id
        if diagnostic:
            job.diagnostic = diagnostic
        job.apply_status_info(status_info)
        await self._repo.update(job)
        await self._repo.append_status(job.id, status_info)
        logger.debug(f"[job:finalize] job_id={job.id} status={status_info.status} remote_status_url={job.remote_status_url} remote_job_id={job.remote_job_id} terminal={job.is_in_terminal_state()}")

        if job.remote_status_url and not job.is_in_terminal_state():
            self._schedule_poll(job.id)

    def _response(self, job_id: str, status_info: Optional[JobStatusInfo]) -> Dict[str, Any]:
        body = status_info.model_dump() if status_info else {}
        return {"status": 201, "headers": {"Location": f"/jobs/{job_id}"}, "body": body}

    async def _resolve_provider(self, process_id: str) -> tuple[str, str]:
        try:
            provider_prefix, raw_id = self._validator.extract(process_id)
            return provider_prefix, raw_id
        except ValueError:
            # search summaries as fallback
            # For simplicity reuse provider list; a proper search could use cached summaries.
            for name in self._providers.list_providers():
                # naive attempt: assume raw_id exists under provider
                return name, process_id
            raise OGCProcessException(
                OGCExceptionResponse(
                    type="about:blank",
                    title="Not Found",
                    status=404,
                    detail=f"Process '{process_id}' not found",
                    instance=None,
                )
            )

    def _extract_status_info(self, body: Any) -> Optional[JobStatusInfo]:
        if not isinstance(body, dict):
            return None
        if not REQUIRED_STATUS_FIELDS.issubset(body.keys()):
            return None
        try:
            return JobStatusInfo(**body)
        except Exception:
            return None

    def _resolve_location(self, base: str, location: str) -> str:
        if location.startswith("http://") or location.startswith("https://"):
            return location
        return urljoin(base.rstrip("/") + "/", location.lstrip("/"))

    def _is_inline_small(self, inputs: Dict[str, Any]) -> bool:
        # simplistic size heuristic; refine later
        return len(str(inputs)) < 1024 * 64

    # ---------------- Polling -----------------
    def _schedule_poll(self, job_id: str) -> None:
        if self._shutdown:
            return
        logger.debug(f"[job:poll] scheduling poll loop job_id={job_id}")
        task = asyncio.create_task(self._poll_loop(job_id))
        self._poll_tasks.add(task)
        task.add_done_callback(lambda t: self._poll_tasks.discard(t))

    async def _poll_loop(self, job_id: str) -> None:
        """Continuously poll remote status until terminal or shutdown.

        Uses fixed interval from settings; could be enhanced with exponential backoff.
        """
        try:
            while not self._shutdown:
                job = await self._repo.get(job_id)

                if not job:
                    logger.debug(f"[job:poll] job disappeared job_id={job_id} stopping")
                    return

                if job.is_in_terminal_state():
                    logger.debug(f"[job:poll] terminal state reached job_id={job_id} status={job.status}")
                    return

                if not job.remote_status_url:
                    logger.debug(f"[job:poll] no remote_status_url job_id={job_id} stopping")
                    return

                try:
                    resp = await self._http.get(job.remote_status_url)
                    status_info = self._extract_status_info(resp)
                    if status_info:
                        # Keep remote IDs consistent
                        if status_info.jobID and status_info.jobID != job.id:
                            if not job.remote_job_id:
                                job.remote_job_id = status_info.jobID
                            status_info.jobID = job.id
                        status_info.processID = job.process_id
                        
                        job.apply_status_info(status_info)
                        
                        await self._repo.update(job)
                        await self._repo.append_status(job.id, status_info)
                        
                        if job.is_in_terminal_state():
                            logger.debug(f"[job:poll] reached terminal state job_id={job.id} status={job.status}")
                            return
                except Exception as poll_err:
                    logger.debug(f"[job:poll] error job_id={job_id} err={poll_err}")
                await asyncio.sleep(self._poll_interval)
        finally:
            pass

    async def shutdown(self) -> None:
        self._shutdown = True
        for task in list(self._poll_tasks):
            task.cancel()
        if self._poll_tasks:
            await asyncio.gather(*self._poll_tasks, return_exceptions=True)
