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

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set
from urllib.parse import urljoin

from ump.core.config import JobManagerConfig
from ump.core.exceptions import OGCProcessException, JobTimeoutError, ResultsFetchError
from ump.core.interfaces.http_client import HttpClientPort
from ump.core.interfaces.job_repository import JobRepositoryPort
from ump.core.interfaces.process_id_validator import ProcessIdValidatorPort
from ump.core.interfaces.providers import ProvidersPort
from ump.core.interfaces.status_derivation import StatusDerivationContext
from ump.core.managers.status_derivation_orchestrator import StatusDerivationOrchestrator
from ump.core.models.job import Job, JobStatusInfo, StatusCode
from ump.core.models.link import Link
from ump.core.models.ogcp_exception import OGCExceptionResponse
from ump.core.settings import logger

REQUIRED_STATUS_FIELDS = {"jobID", "status", "type"}


class JobManager:
    """Orchestrates job lifecycle: creation, forwarding, status derivation, polling, results proxy.
    
    Attributes:
        config: Immutable configuration for job behavior (poll intervals, timeouts, etc.)
    """
    
    def __init__(
        self,
        providers: ProvidersPort,
        http_client: HttpClientPort,
        process_id_validator: ProcessIdValidatorPort,
        job_repo: JobRepositoryPort,
        config: JobManagerConfig,
        retry_port: Optional[Any] = None,  # RetryPort protocol; kept generic to avoid tight coupling
        result_storage_port: Optional[Any] = None,  # ResultStoragePort protocol
    ) -> None:
        self._providers = providers
        self._http = http_client
        self._validator = process_id_validator
        self._repo = job_repo
        self.config = config
        self._poll_tasks: Set[asyncio.Task] = set()
        self._shutdown = False
        self._retry = retry_port
        self._result_storage = result_storage_port
        
        # Initialize status derivation orchestrator
        self._status_orchestrator = StatusDerivationOrchestrator(http_client)

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
        logger.info(
            f"[job:create] incoming execute request for process_id={process_id} headers_prefer={headers.get('Prefer') or headers.get('prefer')}"
        )
        provider_prefix, raw_id = await self._resolve_provider(process_id)
        provider = self._providers.get_provider(provider_prefix)
        logger.debug(
            f"[job:create] resolved provider prefix={provider_prefix} raw_id={raw_id} provider_url={getattr(provider, 'url', None)}"
        )

        inputs = (
            execute_payload.get("inputs") if isinstance(execute_payload, dict) else None
        )
        if inputs:
            logger.debug(
                f"[job:create] inputs keys={list(inputs.keys())[:8]} total_keys={len(inputs.keys())}"
            )
        job = await self._init_job(process_id, provider_prefix, inputs)
        logger.debug(
            f"[job:create] initialized local job id={job.id} inline_inputs={'yes' if job.inputs else 'no'}"
        )
        accepted_si = await self._persist_accepted(job, process_id)
        logger.debug(
            f"[job:create] persisted accepted snapshot job_id={job.id} created={accepted_si.created}"
        )

        prefer = headers.get("Prefer") or headers.get("prefer")
        forward_headers = {"Prefer": prefer} if prefer else {}

        exec_url = str(provider.url).rstrip("/") + f"/processes/{raw_id}/execution"
        logger.debug(
            f"[job:forward] forwarding to exec_url={exec_url} prefer={prefer} payload_keys={list(execute_payload.keys()) if isinstance(execute_payload, dict) else 'n/a'}"
        )

        provider_resp = await self._safe_forward(
            job, exec_url, execute_payload or {}, forward_headers
        )

        # Handle immediate forward failure
        if provider_resp is None:
            failed_job = await self._repo.get(job.id)
            logger.debug(
                f"[job:forward] upstream forward failed immediately job_id={job.id} returning failed status"
            )
            return self._response(
                job.id,
                failed_job.status_info if failed_job and failed_job.status_info else None,
            )

        # Handle upstream error responses (>=400) with non-statusInfo bodies
        upstream_status = provider_resp.get("status")
        upstream_body = provider_resp.get("body")
        logger.debug(
            f"[job:forward] upstream response status={upstream_status} has_location={bool(provider_resp.get('headers', {}).get('Location'))} body_type={type(upstream_body).__name__}"
        )
        
        if upstream_status:
            error_response = await self._handle_upstream_error_response(
                job, upstream_status, upstream_body
            )
            if error_response:
                return error_response

        (
            status_info,
            remote_status_url,
            remote_job_id,
            diagnostic,
        ) = await self._derive_status_info(
            job, process_id, provider, provider_resp, accepted_si
        )
        logger.debug(
            f"[job:derive] job_id={job.id} derived_status={status_info.status if status_info else None} remote_status_url={remote_status_url} remote_job_id={remote_job_id} diagnostic_set={bool(diagnostic)}"
        )

        # Inject local timestamps if remote snapshot omitted them
        if status_info and status_info.created is None:
            status_info.created = accepted_si.created
        if status_info and status_info.updated is None:
            status_info.updated = datetime.now(timezone.utc)

        # If remote reports immediate success, verify results before accepting
        if (
            status_info
            and status_info.status == StatusCode.successful
            and remote_job_id
        ):
            logger.debug(
                f"[job:verify] remote immediate success; verifying results job_id={job.id} remote_job_id={remote_job_id}"
            )
            verified = await self._verify_remote_results(
                provider, process_id, remote_job_id
            )
            if not verified:
                logger.warning(
                    f"[job:verify] results fetch failed; downgrading to failed job_id={job.id}"
                )
                status_info.status = StatusCode.failed
                status_info.message = "Result fetch failed after remote success"
                diagnostic = (diagnostic or "") + " | result fetch failed"

        await self._finalize_job(
            job, status_info, remote_status_url, remote_job_id, diagnostic
        )
        # Return initial accepted snapshot (client can poll for transition)
        return self._response(job.id, accepted_si)

    # ----------------- Helper methods -----------------
    def _enrich_status_info(
        self,
        status_info: JobStatusInfo,
        job: Job,
        accepted_created: datetime,
    ) -> None:
        """Enrich status info with contextual fields based on current status.
        
        Fills in missing timestamps, progress, and messages for consistent UX.
        Modifies status_info in place.
        """
        now = datetime.now(timezone.utc)
        
        if status_info.status == StatusCode.running:
            if status_info.started is None:
                status_info.started = accepted_created
            if status_info.progress is None:
                status_info.progress = 0
            if not status_info.message:
                status_info.message = "Running"
        elif status_info.status == StatusCode.successful:
            if status_info.started is None:
                status_info.started = accepted_created
            if status_info.finished is None:
                status_info.finished = now
            if status_info.progress is None:
                status_info.progress = 100
            if not status_info.message:
                status_info.message = "Completed"
        elif status_info.status == StatusCode.failed:
            if status_info.finished is None:
                status_info.finished = now
            if not status_info.message:
                status_info.message = "Failed"

    def _normalize_and_enrich_status_info(
        self,
        status_info: JobStatusInfo,
        job: Job,
        process_id: str,
        accepted_si: JobStatusInfo,
    ) -> None:
        """Normalize and enrich valid statusInfo with local context.
        
        Modifies status_info in place to:
        - Ensure processID is set correctly
        - Adopt accepted created timestamp if remote omitted it
        - Update updated timestamp
        - Enrich missing optional fields (started, finished, progress, message)
        """
        status_info.processID = process_id
        
        # Adopt accepted created timestamp if remote omitted it
        if status_info.created is None:
            status_info.created = accepted_si.created
        status_info.updated = datetime.now(timezone.utc)
        
        # Enrich missing optional fields
        created_time = accepted_si.created or datetime.now(timezone.utc)
        self._enrich_status_info(status_info, job, created_time)

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
            inputs_storage="inline"
            if inputs and self._is_inline_small(inputs)
            else "object"
            if inputs
            else "inline",
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
        # Always include self link immediately for discoverability
        from ump.core.models.link import Link
        accepted_si.links = [
            Link(href=f"/jobs/{job.id}", rel="self", type="application/json", title="Job status")
        ]
        job.apply_status_info(accepted_si)
        await self._repo.create(job)
        await self._repo.append_status(job.id, accepted_si)
        return accepted_si

    async def _handle_forward_error(
        self, job: Job, exc: Exception
    ) -> None:
        """Handle exceptions during forward request, marking job as failed."""
        if isinstance(exc, OGCProcessException):
            await self._repo.mark_failed(
                job.id, reason=exc.response.title, diagnostic=exc.response.detail
            )
            logger.warning(
                f"[job:forward] OGCProcessException job_id={job.id} title={exc.response.title}"
            )
        else:
            await self._repo.mark_failed(
                job.id, reason="Upstream Error", diagnostic=str(exc)
            )
            logger.error(
                f"[job:forward] unexpected exception job_id={job.id} error={exc}"
            )

    async def _safe_forward(
        self, job: Job, exec_url: str, payload: Dict[str, Any], headers: Dict[str, str]
    ) -> Optional[Dict[str, Any]]:
        """Forward execution request to remote provider with error handling."""
        try:
            logger.debug(
                f"[job:forward] POST exec_url={exec_url} job_id={job.id} headers={list(headers.keys())} payload_size={len(str(payload))}"
            )
            resp = await self._http.post(exec_url, json=payload, headers=headers)
            logger.debug(
                f"[job:forward] POST completed job_id={job.id} status={resp.get('status')} keys={list(resp.keys())}"
            )
            return resp
        except Exception as exc:
            await self._handle_forward_error(job, exc)
            return None

    async def _derive_status_info(
        self,
        job: Job,
        process_id: str,
        provider: Any,
        provider_resp: Dict[str, Any],
        accepted_si: JobStatusInfo,
    ) -> tuple[JobStatusInfo, Optional[str], Optional[str], Optional[str]]:
        """Derive statusInfo from provider response using Strategy pattern.
        
        Delegates to StatusDerivationOrchestrator which selects the appropriate
        strategy based on response pattern (direct statusInfo, immediate results,
        Location follow-up, or fallback failed).
        
        Returns (status_info, remote_status_url, remote_job_id, diagnostic).
        """
        # Create context for strategy evaluation
        context = StatusDerivationContext(
            job=job,
            process_id=process_id,
            provider=provider,
            provider_resp=provider_resp,
            accepted_si=accepted_si,
        )
        
        # Use orchestrator to derive status via appropriate strategy
        result = await self._status_orchestrator.derive_status(context)
        
        # Normalize and enrich if we got valid statusInfo
        if result.status_info and result.status_info.status != StatusCode.failed:
            self._normalize_and_enrich_status_info(
                result.status_info, job, process_id, accepted_si
            )
        
        # Ensure local self link consistency for any status
        self._ensure_self_link(job.id, result.status_info)
        
        return (
            result.status_info,
            result.remote_status_url,
            result.remote_job_id,
            result.diagnostic,
        )

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
        # Inject local results link if job already successful and link absent
        if status_info and status_info.status == StatusCode.successful:
            self._ensure_self_link(job.id, status_info)
            self._ensure_results_link(job.id, status_info)
        job.apply_status_info(status_info)
        await self._repo.update(job)
        await self._repo.append_status(job.id, status_info)
        logger.debug(
            f"[job:finalize] job_id={job.id} status={status_info.status} remote_status_url={job.remote_status_url} remote_job_id={job.remote_job_id} terminal={job.is_in_terminal_state()}"
        )

        if job.remote_status_url and not job.is_in_terminal_state():
            self._schedule_poll(job.id)

    async def _handle_upstream_error_response(
        self, job: Job, upstream_status: int, upstream_body: Any
    ) -> Optional[Dict[str, Any]]:
        """Handle error responses (>=400) from upstream provider.
        
        Returns propagated error response dict if body is not statusInfo, None otherwise.
        """
        if upstream_status < 400:
            return None
        
        si = self._extract_status_info(upstream_body)
        if si:
            # Valid statusInfo in error response; will be handled normally
            return None
        
        # Non-statusInfo error body; mark local job failed and propagate upstream response
        await self._repo.mark_failed(job.id, reason=f"Upstream {upstream_status}")
        logger.debug(
            f"[job:error-propagate] marking job failed job_id={job.id} upstream_status={upstream_status} returning raw upstream body"
        )
        
        return {
            "status": upstream_status,
            "headers": {"Location": f"/jobs/{job.id}"},
            "body": upstream_body if isinstance(upstream_body, (dict, list)) else {"error": str(upstream_body)},
        }

    def _response(
        self, job_id: str, status_info: Optional[JobStatusInfo]
    ) -> Dict[str, Any]:
        body = status_info.model_dump() if status_info else {}
        return {"status": 201, "headers": {"Location": f"/jobs/{job_id}"}, "body": body}

    async def _verify_remote_results(
        self, provider: Any, process_id: str, remote_job_id: str
    ) -> bool:
        """Fetch remote results for terminal successful job; return True if fetched.

        Failure to fetch indicates mismatch between remote status and availability; we
        treat this as local failure to ensure clients don't assume success without outputs.
        """
        try:

            base = str(provider.url).rstrip("/")
            results_url = f"{base}/jobs/{remote_job_id}/results"
            logger.debug(f"[job:verify] fetching results_url={results_url}")

            async def fetch():
                return await self._http.get(results_url)

            # Use injected retry adapter if available (supports transient unavailability right after success)
            if self._retry:
                try:
                    resp = await self._retry.execute(fetch)
                except Exception as exc:
                    logger.debug(
                        f"[job:verify] retry exhausted job_id={remote_job_id} err={exc}"
                    )
                    return False
            else:
                # Fallback single attempt
                resp = await fetch()

            if isinstance(resp, dict):
                logger.debug(
                    f"[job:verify] results fetch ok keys={list(resp.keys())[:5]}"
                )
                return True
            logger.debug(
                f"[job:verify] results non-dict type={type(resp).__name__}; treating as success"
            )
            return True
        except Exception as exc:
            logger.debug(
                f"[job:verify] results fetch exception job_id={remote_job_id} err={exc}"
            )
            return False

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
        """Check if inputs are small enough for inline storage."""
        return len(str(inputs)) < self.config.inline_inputs_size_limit

    async def _check_and_handle_timeout(self, job: Job) -> bool:
        """Check if job has exceeded timeout and mark as failed if so.
        
        Returns True if timeout was reached and job was marked failed.
        """
        if self.config.poll_timeout is None or job.created is None:
            return False
        
        elapsed = (datetime.now(timezone.utc) - job.created).total_seconds()
        if elapsed <= self.config.poll_timeout:
            return False
        
        logger.warning(
            f"[job:poll] timeout reached job_id={job.id} elapsed={elapsed}s > {self.config.poll_timeout}s; marking failed"
        )
        
        timeout_si = JobStatusInfo(
            jobID=job.id,
            status=StatusCode.failed,
            type="process",
            processID=job.process_id,
            message=f"Timed out after {self.config.poll_timeout}s waiting for remote completion",
            created=job.created,
            updated=datetime.now(timezone.utc),
            finished=datetime.now(timezone.utc),
            progress=None,
        )
        
        job.apply_status_info(timeout_si)
        await self._repo.update(job)
        await self._repo.append_status(job.id, timeout_si)
        return True

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
                    logger.debug(
                        f"[job:poll] terminal state reached job_id={job_id} status={job.status}"
                    )
                    return

                if not job.remote_status_url:
                    logger.debug(
                        f"[job:poll] no remote_status_url job_id={job_id} stopping"
                    )
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
                        
                        prev_status = job.status_info.status if job.status_info else None
                        status_info.processID = job.process_id
                        
                        # Enrich on status change or missing fields
                        needs_enrichment = (
                            prev_status != status_info.status or
                            any(getattr(status_info, f) is None for f in ["started", "progress", "message"])
                        )
                        if needs_enrichment:
                            created_time = job.created or datetime.now(timezone.utc)
                            self._enrich_status_info(status_info, job, created_time)
                        
                        status_info.updated = datetime.now(timezone.utc)
                        
                        # Ensure local links
                        self._ensure_self_link(job.id, status_info)
                        if status_info.status == StatusCode.successful:
                            self._ensure_results_link(job.id, status_info)
                        
                        job.apply_status_info(status_info)
                        await self._repo.update(job)
                        await self._repo.append_status(job.id, status_info)

                        if job.is_in_terminal_state():
                            logger.debug(
                                f"[job:poll] reached terminal state job_id={job.id} status={job.status}"
                            )
                            return
                            
                except Exception as poll_err:
                    logger.debug(f"[job:poll] error job_id={job_id} err={poll_err}")
                
                # Check for timeout and mark failed if exceeded
                if await self._check_and_handle_timeout(job):
                    return
                
                await asyncio.sleep(self.config.poll_interval)
        finally:
            pass

    async def shutdown(self) -> None:
        self._shutdown = True
        for task in list(self._poll_tasks):
            task.cancel()
        if self._poll_tasks:
            await asyncio.gather(*self._poll_tasks, return_exceptions=True)

    # ---------------- Results Access -----------------
    async def get_results(self, job_id: str) -> Dict[str, Any]:
        """Fetch remote results for a terminal successful job.

        We never persist results locally; every invocation proxies the provider.
        Returns provider JSON (dict). Raises OGCProcessException for upstream
        OGC errors; returns 404 style dict if job not found or not successful.
        """
        job = await self._repo.get(job_id)
        if not job or not job.status_info:
            return {"status": 404, "body": {"detail": "Job not found"}}
        if job.status_info.status != StatusCode.successful:
            return {"status": 404, "body": {"detail": "Results not available"}}
        if not job.remote_job_id or not job.provider:
            return {"status": 404, "body": {"detail": "Remote job id missing"}}
        provider = self._providers.get_provider(job.provider)
        base = str(provider.url).rstrip("/")
        results_url = f"{base}/jobs/{job.remote_job_id}/results"
        logger.debug(
            f"[job:results] proxy fetch results_url={results_url} job_id={job.id}"
        )
        try:
            resp = await self._http.get(results_url)
            # Normalize into dict response
            body = resp if isinstance(resp, dict) else {"raw": resp}
            return {"status": 200, "body": body}
        except OGCProcessException as exc:
            # Bubble upstream OGC error (already structured) to adapter layer
            raise exc
        except Exception as exc:
            logger.error(f"[job:results] unexpected error job_id={job.id} err={exc}")
            return {
                "status": 500,
                "body": {"detail": "Unexpected error fetching results"},
            }

    # ---------------- Link Helpers -----------------
    def _ensure_results_link(self, job_id: str, status_info: JobStatusInfo) -> None:
        """Ensure a relative results link is present in statusInfo.links when successful."""
        if status_info.status != StatusCode.successful:
            return
        existing = status_info.links or []
        if any(l.rel == "results" for l in existing):
            return
        results_link = Link(
            href=f"/jobs/{job_id}/results",
            rel="results",
            type="application/json",
            title="Job results",
        )
        status_info.links = existing + [results_link]
    
    def _ensure_self_link(self, job_id: str, status_info: JobStatusInfo) -> None:
        """Guarantee a local self link (remove remote self/results with foreign job id)."""
        existing = status_info.links or []
        filtered = [
            l
            for l in existing
            if not (l.rel in {"self", "results"} and f"/jobs/{job_id}" not in (l.href or ""))
        ]
        if any(l.rel == "self" for l in filtered):
            status_info.links = filtered
            return
        self_link = Link(
            href=f"/jobs/{job_id}",
            rel="self",
            type="application/json",
            title="Job status",
        )
        status_info.links = filtered + [self_link]
