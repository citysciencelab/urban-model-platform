"""Concrete observer implementations for job state transitions.

This module provides production-ready observers that handle:
- Status history recording
- Background polling scheduling
- Results verification
"""

import asyncio
import logging
from typing import Optional, Set

from ump.core.models.job import Job, JobStatusInfo, StatusCode
from ump.core.interfaces.observers import JobStateObserver
from ump.core.interfaces.job_repository import JobRepositoryPort
from ump.core.interfaces.http_client import HttpClientPort


logger = logging.getLogger(__name__)


class StatusHistoryObserver:
    """Records all status changes to job repository.
    
    Extracts status history recording from JobManager, making it an explicit
    side effect that can be enabled/disabled independently.
    """
    
    def __init__(self, repository: JobRepositoryPort):
        self._repo = repository
    
    async def on_job_created(
        self,
        job: Job,
        status_info: JobStatusInfo,
    ) -> None:
        """Record initial status in history."""
        await self._repo.append_status(job.id, status_info)
        logger.debug(f"[observer:history] recorded initial status job_id={job.id} status={status_info.status}")
    
    async def on_status_changed(
        self,
        job: Job,
        old_status_info: Optional[JobStatusInfo],
        new_status_info: JobStatusInfo,
    ) -> None:
        """Record status change in history."""
        await self._repo.append_status(job.id, new_status_info)
        logger.debug(
            f"[observer:history] recorded status change job_id={job.id} "
            f"old={old_status_info.status if old_status_info else None} new={new_status_info.status}"
        )
    
    async def on_job_completed(
        self,
        job: Job,
        final_status_info: JobStatusInfo,
    ) -> None:
        """Terminal status already recorded in on_status_changed."""
        pass


class PollingSchedulerObserver:
    """Schedules background polling for running jobs.
    
    Extracts polling scheduling decision from JobManager, decoupling state
    observation from implementation. The actual poll loop remains in JobManager
    as it requires complex dependencies (status derivation, enrichment, etc.).
    
    This observer makes the "when to start polling" decision explicit and
    testable without duplicating complex polling logic.
    """
    
    def __init__(self, schedule_callback):
        """Initialize with callback to JobManager._schedule_poll method.
        
        Args:
            schedule_callback: Callable that schedules a poll loop for a job_id
        """
        self._schedule_callback = schedule_callback
    
    async def on_job_created(
        self,
        job: Job,
        status_info: JobStatusInfo,
    ) -> None:
        """Job creation doesn't trigger polling (wait for status change)."""
        pass
    
    async def on_status_changed(
        self,
        job: Job,
        old_status_info: Optional[JobStatusInfo],
        new_status_info: JobStatusInfo,
    ) -> None:
        """Schedule polling if job is running with remote status URL."""
        if job.remote_status_url and not job.is_in_terminal_state():
            logger.debug(f"[observer:polling] triggering poll schedule job_id={job.id}")
            self._schedule_callback(job.id)
    
    async def on_job_completed(
        self,
        job: Job,
        final_status_info: JobStatusInfo,
    ) -> None:
        """Terminal jobs don't need polling."""
        pass


class ResultsVerificationObserver:
    """Verifies remote results are accessible for successful jobs.
    
    Extracts results verification from JobManager, making it a separate
    concern that can be enabled/disabled independently.
    """
    
    def __init__(self, http_client: HttpClientPort):
        self._http = http_client
    
    async def on_job_created(
        self,
        job: Job,
        status_info: JobStatusInfo,
    ) -> None:
        """Job creation doesn't trigger verification."""
        pass
    
    async def on_status_changed(
        self,
        job: Job,
        old_status_info: Optional[JobStatusInfo],
        new_status_info: JobStatusInfo,
    ) -> None:
        """Status changes don't trigger verification (wait for completion)."""
        pass
    
    async def on_job_completed(
        self,
        job: Job,
        final_status_info: JobStatusInfo,
    ) -> None:
        """Verify remote results are accessible for successful jobs."""
        if final_status_info.status != StatusCode.successful:
            return
        
        # Extract results URL from status info links
        results_url = None
        if final_status_info.links:
            for link in final_status_info.links:
                if link.rel == "results":
                    results_url = link.href
                    break
        
        if not results_url:
            logger.debug(f"[observer:verify] no results URL job_id={job.id}")
            return
        
        # Skip verification for local results (already served by this API)
        if results_url.startswith("/jobs/"):
            logger.debug(f"[observer:verify] skipping local results job_id={job.id}")
            return
        
        # Verify remote results are accessible
        try:
            logger.debug(f"[observer:verify] checking remote results job_id={job.id} url={results_url}")
            await self._http.get(results_url, timeout=10.0)
            logger.debug(f"[observer:verify] remote results accessible job_id={job.id}")
        except Exception as exc:
            logger.warning(
                f"[observer:verify] remote results check failed job_id={job.id} "
                f"url={results_url} error={exc}"
            )
            # Don't fail the job, just log warning
