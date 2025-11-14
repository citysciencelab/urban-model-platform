"""Observer protocols for job state transitions.

This module defines the Observer pattern for reacting to job lifecycle events.
Observers decouple side effects (polling, history recording, verification) from
core job management logic, improving maintainability and testability.
"""

from typing import Protocol, Optional
from ump.core.models.job import Job, JobStatusInfo


class JobStateObserver(Protocol):
    """Observer protocol for job state transitions.
    
    Implementations can react to job lifecycle events:
    - on_job_created: After job is created and initial status stored
    - on_status_changed: After job status is updated (including history)
    - on_job_completed: After job reaches terminal state (success/failed)
    
    Observers should be stateless or thread-safe, as they may be called
    from multiple async tasks (e.g., during concurrent polling).
    """
    
    async def on_job_created(
        self,
        job: Job,
        status_info: JobStatusInfo,
    ) -> None:
        """Called after job is created with initial accepted status.
        
        Args:
            job: The newly created job
            status_info: Initial status (typically 'accepted')
        """
        ...
    
    async def on_status_changed(
        self,
        job: Job,
        old_status_info: Optional[JobStatusInfo],
        new_status_info: JobStatusInfo,
    ) -> None:
        """Called after job status changes.
        
        Args:
            job: The job with updated status
            old_status_info: Previous status (None if first status)
            new_status_info: New status
        """
        ...
    
    async def on_job_completed(
        self,
        job: Job,
        final_status_info: JobStatusInfo,
    ) -> None:
        """Called after job reaches terminal state.
        
        Args:
            job: The completed job
            final_status_info: Final status (successful/failed)
        """
        ...
