"""JobManager: orchestrates local job creation and remote execution forwarding.

Step 1 implementation:
 - Always creates a local Job with status 'accepted'.
 - Forwards execution to provider.
 - Attempts to capture provider statusInfo directly from body; otherwise follows Location header.
 - Updates Job.status_info and persists snapshot via JobRepository.
 - Returns (job, status_info) where status_info is the latest snapshot (may be failure fallback).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set
from urllib.parse import urljoin

from ump.core.exceptions import OGCProcessException
from ump.core.interfaces.http_client import HttpClientPort
from ump.core.interfaces.job_repository import JobRepositoryPort
from ump.core.interfaces.process_id_validator import ProcessIdValidatorPort
from ump.core.interfaces.providers import ProvidersPort
from ump.core.models.job import Job, JobStatusInfo, StatusCode
from ump.core.models.ogcp_exception import OGCExceptionResponse
from ump.core.settings import app_settings, logger

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
        self._poll_interval = getattr(
            app_settings, "UMP_REMOTE_JOB_STATUS_REQUEST_INTERVAL", 5
        )
        self._poll_tasks: Set[asyncio.Task] = set()
        self._shutdown = False

    async def create_and_forward(
        self,
        process_id: str,
        exec_body: Optional[Dict[str, Any]],
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        """Create local job, forward execute, update status, return API response dict.

        Response dict keys: status (HTTP), headers, body (statusInfo payload)
        """
        provider_prefix, raw_id = await self._resolve_provider(process_id)
        provider = self._providers.get_provider(provider_prefix)

        job_id = str(uuid.uuid4())
        job = Job(
            id=job_id,
            process_id=process_id,
            provider=provider_prefix,
            status=str(StatusCode.accepted),
            inputs=exec_body if exec_body and self._is_inline_small(exec_body) else None,
            inputs_storage=(
                "inline"
                if exec_body and self._is_inline_small(exec_body)
                else "object"
                if exec_body
                else "inline"
            ),
        )

        # initial status snapshot (accepted)
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

        # store job
        await self._repo.create(job)
        await self._repo.append_status(job.id, accepted_si)

        # Forward execute request to provider
        prefer = headers.get("Prefer") or headers.get("prefer")
        forward_headers = {}
        if prefer:
            forward_headers["Prefer"] = prefer

        exec_url = f"{str(provider.url).rstrip('/')}/processes/{raw_id}/execution"

        try:
            provider_resp = await self._http.post(
                exec_url, json=exec_body or {}, headers=forward_headers
            )
        except OGCProcessException as exc:
            # mark job failed and return failure snapshot
            await self._repo.mark_failed(
                job.id, reason=exc.response.title, diagnostic=exc.response.detail
            )
            failed_job = await self._repo.get(job.id)
            return {
                "status": 201,
                "headers": {"Location": f"/jobs/{job_id}"},
                "body": failed_job.status_info.model_dump()
                if failed_job and failed_job.status_info
                else {},
            }
        except Exception as exc:
            await self._repo.mark_failed(
                job.id, reason="Upstream Error", diagnostic=str(exc)
            )
            failed_job = await self._repo.get(job.id)
            return {
                "status": 201,
                "headers": {"Location": f"/jobs/{job_id}"},
                "body": failed_job.status_info.model_dump()
                if failed_job and failed_job.status_info
                else {},
            }

        # Parse provider response
        provider_status = provider_resp.get("status")
        provider_headers = provider_resp.get("headers", {})
        provider_body = provider_resp.get("body")

        status_info = self._extract_status_info(provider_body)
        remote_status_url: Optional[str] = None
        remote_job_id: Optional[str] = None

        if not status_info and provider_headers.get("Location"):
            # Follow Location
            location = provider_headers["Location"]
            resolved = self._resolve_location(str(provider.url), location)
            remote_status_url = resolved
            try:
                follow_resp = await self._http.get(resolved)
                status_info = self._extract_status_info(follow_resp)
            except Exception as follow_err:
                logger.warning(
                    f"Failed to follow provider Location {location}: {follow_err}"
                )

        if not status_info:
            # create failure snapshot if provider did not supply valid statusInfo
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
            job.diagnostic = (
                f"provider_status={provider_status} body_type={type(provider_body).__name__}"
            )
        else:
            # Ensure jobID consistency; capture remote job ID if different
            if status_info.jobID and status_info.jobID != job.id:
                remote_job_id = status_info.jobID
                status_info.jobID = job.id
            status_info.processID = process_id

        # Persist remote identifiers for polling if available
        if remote_status_url:
            job.remote_status_url = remote_status_url
        if remote_job_id:
            job.remote_job_id = remote_job_id
        job.apply_status_info(status_info)
        await self._repo.update(job)
        await self._repo.append_status(job.id, status_info)

        # Schedule polling if not terminal and we have a status URL
        if job.remote_status_url and not job.is_in_terminal_state():
            self._schedule_poll(job.id)

        return {
            "status": 201,
            "headers": {"Location": f"/jobs/{job.id}"},
            "body": status_info.model_dump(),
        }

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
                    return
                if job.is_in_terminal_state():
                    return
                if not job.remote_status_url:
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
                            return
                except Exception as poll_err:
                    logger.debug(f"Polling error for job {job_id}: {poll_err}")
                await asyncio.sleep(self._poll_interval)
        finally:
            pass

    async def shutdown(self) -> None:
        self._shutdown = True
        for task in list(self._poll_tasks):
            task.cancel()
        if self._poll_tasks:
            await asyncio.gather(*self._poll_tasks, return_exceptions=True)
