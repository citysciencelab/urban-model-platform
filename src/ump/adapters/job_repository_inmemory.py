"""In-memory implementation of JobRepositoryPort.

Thread-safe / async-safe using an asyncio.Lock. Suitable for TDD and local tests.
Not intended for production; replace with SQLModel/Postgres adapter.
"""
from __future__ import annotations

import asyncio
from typing import Dict, Optional, Sequence, List
from copy import deepcopy
from datetime import datetime, timezone

from ump.core.interfaces.job_repository import JobRepositoryPort
from ump.core.models.job import Job, JobStatusInfo, StatusCode


class InMemoryJobRepository(JobRepositoryPort):
    def __init__(self) -> None:
        self._jobs: Dict[str, Job] = {}
        self._status_history: Dict[str, List[JobStatusInfo]] = {}
        self._events: Dict[str, List[dict]] = {}
        self._lock = asyncio.Lock()

    async def create(self, job: Job) -> Job:
        async with self._lock:
            if job.id in self._jobs:
                raise ValueError(f"Job already exists: {job.id}")
            # ensure timestamps
            if not job.created:
                job.created = datetime.now(timezone.utc)
            stored = deepcopy(job)
            self._jobs[job.id] = stored
            if stored.status_info:
                self._status_history.setdefault(job.id, []).append(deepcopy(stored.status_info))
            else:
                self._status_history.setdefault(job.id, [])
            self._events.setdefault(job.id, [])
            return deepcopy(stored)

    async def get(self, job_id: str) -> Optional[Job]:
        async with self._lock:
            j = self._jobs.get(job_id)
            return deepcopy(j) if j else None

    async def update(self, job: Job) -> Job:
        async with self._lock:
            if job.id not in self._jobs:
                raise KeyError(job.id)
            job.touch()
            stored = deepcopy(job)
            self._jobs[job.id] = stored
            # status snapshot updated separately via append_status to avoid duplication
            return deepcopy(stored)

    async def list(
        self,
        provider: Optional[str] = None,
        process_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Sequence[Job]:
        async with self._lock:
            jobs = list(self._jobs.values())
            if provider is not None:
                jobs = [j for j in jobs if j.provider == provider]
            if process_id is not None:
                jobs = [j for j in jobs if j.process_id == process_id]
            if status is not None:
                jobs = [j for j in jobs if j.status == status]
            return [deepcopy(j) for j in jobs]

    async def mark_failed(self, job_id: str, reason: str, diagnostic: Optional[str] = None) -> Optional[Job]:
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            # construct a statusInfo snapshot indicating failure
            status_info = JobStatusInfo(
                jobID=job.id,
                status=StatusCode.failed,
                message=reason,
                updated=datetime.now(timezone.utc),
                created=job.created,
                progress=None,
            )
            job.apply_status_info(status_info)
            if diagnostic:
                job.diagnostic = diagnostic
            self._status_history[job.id].append(deepcopy(status_info))
            self._jobs[job.id] = deepcopy(job)
            return deepcopy(job)

    async def append_status(self, job_id: str, status_info: JobStatusInfo) -> Optional[Job]:
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            job.apply_status_info(status_info)
            self._status_history[job_id].append(deepcopy(status_info))
            self._jobs[job_id] = deepcopy(job)
            return deepcopy(job)

    async def append_event(self, job_id: str, event: dict) -> None:
        async with self._lock:
            if job_id not in self._events:
                # Initialize missing job bucket to avoid exceptions (event before create is rare but safe)
                self._events[job_id] = []
            self._events[job_id].append(deepcopy(event))

    # Convenience accessors (not part of port but useful for tests)
    async def history(self, job_id: str) -> List[JobStatusInfo]:  # pragma: no cover simple access
        async with self._lock:
            return [deepcopy(s) for s in self._status_history.get(job_id, [])]

    async def events(self, job_id: str) -> List[dict]:  # pragma: no cover simple access
        async with self._lock:
            return [deepcopy(e) for e in self._events.get(job_id, [])]
