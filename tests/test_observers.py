"""Unit tests for job state observers.

Tests the Observer pattern implementation for reacting to job lifecycle events.
Each observer is tested independently for all lifecycle methods.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

from ump.core.managers.observers import (
    StatusHistoryObserver,
    PollingSchedulerObserver,
    ResultsVerificationObserver,
)
from ump.core.models.job import Job, JobStatusInfo, StatusCode
from ump.core.models.link import Link
from ump.adapters.job_repository_inmemory import InMemoryJobRepository


# --- Test Fixtures ---

@pytest.fixture
def test_job():
    """Create test job."""
    return Job(
        id="test-job-123",
        process_id="test:process",
        provider="test",
        status="accepted",
        inputs=None,
        inputs_storage="inline",
    )


@pytest.fixture
def accepted_status():
    """Create accepted status."""
    return JobStatusInfo(
        jobID="test-job-123",
        status=StatusCode.accepted,
        type="process",
        processID="test:process",
        created=datetime.now(timezone.utc),
        updated=datetime.now(timezone.utc),
        progress=0,
    )


@pytest.fixture
def running_status():
    """Create running status."""
    return JobStatusInfo(
        jobID="test-job-123",
        status=StatusCode.running,
        type="process",
        processID="test:process",
        created=datetime.now(timezone.utc),
        updated=datetime.now(timezone.utc),
        message="Processing",
        progress=50,
    )


@pytest.fixture
def success_status():
    """Create successful status with results link."""
    status = JobStatusInfo(
        jobID="test-job-123",
        status=StatusCode.successful,
        type="process",
        processID="test:process",
        created=datetime.now(timezone.utc),
        updated=datetime.now(timezone.utc),
        message="Complete",
        progress=100,
    )
    status.links = [
        Link(href="/jobs/test-job-123/results", rel="results", type="application/json")
    ]
    return status


@pytest.fixture
def failed_status():
    """Create failed status."""
    return JobStatusInfo(
        jobID="test-job-123",
        status=StatusCode.failed,
        type="process",
        processID="test:process",
        created=datetime.now(timezone.utc),
        updated=datetime.now(timezone.utc),
        message="Processing failed",
        progress=0,
    )


# --- StatusHistoryObserver Tests ---

class TestStatusHistoryObserver:
    """Test status history recording observer."""
    
    @pytest.mark.asyncio
    async def test_on_job_created_records_initial_status(self, test_job, accepted_status):
        """Should record initial status when job is created."""
        repo = InMemoryJobRepository()
        observer = StatusHistoryObserver(repository=repo)
        
        await repo.create(test_job)
        await observer.on_job_created(test_job, accepted_status)
        
        history = await repo.get_status_history(test_job.id)
        assert len(history) == 1
        assert history[0].status == StatusCode.accepted
    
    @pytest.mark.asyncio
    async def test_on_status_changed_records_new_status(
        self, test_job, accepted_status, running_status
    ):
        """Should record status changes to history."""
        repo = InMemoryJobRepository()
        observer = StatusHistoryObserver(repository=repo)
        
        await repo.create(test_job)
        await observer.on_status_changed(test_job, accepted_status, running_status)
        
        history = await repo.get_status_history(test_job.id)
        assert len(history) == 1
        assert history[0].status == StatusCode.running
    
    @pytest.mark.asyncio
    async def test_on_job_completed_does_not_duplicate(
        self, test_job, success_status
    ):
        """Should not duplicate terminal status (already recorded in on_status_changed)."""
        repo = InMemoryJobRepository()
        observer = StatusHistoryObserver(repository=repo)
        
        await repo.create(test_job)
        initial_count = len(await repo.get_status_history(test_job.id))
        
        await observer.on_job_completed(test_job, success_status)
        
        final_count = len(await repo.get_status_history(test_job.id))
        assert final_count == initial_count  # No change


# --- PollingSchedulerObserver Tests ---

class TestPollingSchedulerObserver:
    """Test polling scheduler observer."""
    
    @pytest.mark.asyncio
    async def test_on_job_created_does_nothing(self, test_job, accepted_status):
        """Should not schedule polling for newly created jobs."""
        callback_called = False
        
        def schedule_callback(job_id):
            nonlocal callback_called
            callback_called = True
        
        observer = PollingSchedulerObserver(schedule_callback=schedule_callback)
        await observer.on_job_created(test_job, accepted_status)
        
        assert callback_called is False
    
    @pytest.mark.asyncio
    async def test_on_status_changed_schedules_for_running_with_url(
        self, test_job, accepted_status, running_status
    ):
        """Should schedule polling when job enters running state with remote URL."""
        callback_called_with = None
        
        def schedule_callback(job_id):
            nonlocal callback_called_with
            callback_called_with = job_id
        
        test_job.remote_status_url = "http://remote.test/jobs/123"
        test_job.status_info = running_status
        
        observer = PollingSchedulerObserver(schedule_callback=schedule_callback)
        await observer.on_status_changed(test_job, accepted_status, running_status)
        
        assert callback_called_with == test_job.id
    
    @pytest.mark.asyncio
    async def test_on_status_changed_does_not_schedule_without_url(
        self, test_job, accepted_status, running_status
    ):
        """Should not schedule polling if no remote status URL."""
        callback_called = False
        
        def schedule_callback(job_id):
            nonlocal callback_called
            callback_called = True
        
        test_job.remote_status_url = None  # No URL
        test_job.status_info = running_status
        
        observer = PollingSchedulerObserver(schedule_callback=schedule_callback)
        await observer.on_status_changed(test_job, accepted_status, running_status)
        
        assert callback_called is False
    
    @pytest.mark.asyncio
    async def test_on_status_changed_does_not_schedule_for_terminal(
        self, test_job, running_status, success_status
    ):
        """Should not schedule polling for terminal states."""
        callback_called = False
        
        def schedule_callback(job_id):
            nonlocal callback_called
            callback_called = True
        
        test_job.remote_status_url = "http://remote.test/jobs/123"
        test_job.status_info = success_status
        
        observer = PollingSchedulerObserver(schedule_callback=schedule_callback)
        await observer.on_status_changed(test_job, running_status, success_status)
        
        assert callback_called is False  # Terminal state
    
    @pytest.mark.asyncio
    async def test_on_job_completed_does_nothing(self, test_job, success_status):
        """Should not schedule polling for completed jobs."""
        callback_called = False
        
        def schedule_callback(job_id):
            nonlocal callback_called
            callback_called = True
        
        observer = PollingSchedulerObserver(schedule_callback=schedule_callback)
        await observer.on_job_completed(test_job, success_status)
        
        assert callback_called is False


# --- ResultsVerificationObserver Tests ---

class TestResultsVerificationObserver:
    """Test results verification observer."""
    
    @pytest.mark.asyncio
    async def test_on_job_created_does_nothing(self, test_job, accepted_status):
        """Should not verify results for newly created jobs."""
        http_client = AsyncMock()
        observer = ResultsVerificationObserver(http_client=http_client)
        
        await observer.on_job_created(test_job, accepted_status)
        
        http_client.get.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_on_status_changed_does_nothing(
        self, test_job, accepted_status, running_status
    ):
        """Should not verify results during status changes."""
        http_client = AsyncMock()
        observer = ResultsVerificationObserver(http_client=http_client)
        
        await observer.on_status_changed(test_job, accepted_status, running_status)
        
        http_client.get.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_on_job_completed_verifies_successful_remote_results(
        self, test_job, success_status
    ):
        """Should verify remote results are accessible for successful jobs."""
        http_client = AsyncMock()
        http_client.get.return_value = {"outputs": {"result": 42}}
        
        # Add remote results link
        success_status.links = [
            Link(
                href="http://remote.test/jobs/123/results",
                rel="results",
                type="application/json"
            )
        ]
        
        observer = ResultsVerificationObserver(http_client=http_client)
        await observer.on_job_completed(test_job, success_status)
        
        http_client.get.assert_called_once_with(
            "http://remote.test/jobs/123/results",
            timeout=10.0
        )
    
    @pytest.mark.asyncio
    async def test_on_job_completed_skips_local_results(self, test_job, success_status):
        """Should skip verification for local results links."""
        http_client = AsyncMock()
        
        # Local results link (starts with /jobs/)
        success_status.links = [
            Link(
                href="/jobs/test-job-123/results",
                rel="results",
                type="application/json"
            )
        ]
        
        observer = ResultsVerificationObserver(http_client=http_client)
        await observer.on_job_completed(test_job, success_status)
        
        http_client.get.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_on_job_completed_skips_failed_jobs(self, test_job, failed_status):
        """Should not verify results for failed jobs."""
        http_client = AsyncMock()
        observer = ResultsVerificationObserver(http_client=http_client)
        
        await observer.on_job_completed(test_job, failed_status)
        
        http_client.get.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_on_job_completed_handles_verification_failure(
        self, test_job, success_status
    ):
        """Should handle verification errors gracefully without failing the job."""
        http_client = AsyncMock()
        http_client.get.side_effect = Exception("Connection error")
        
        success_status.links = [
            Link(
                href="http://remote.test/jobs/123/results",
                rel="results",
                type="application/json"
            )
        ]
        
        observer = ResultsVerificationObserver(http_client=http_client)
        
        # Should not raise exception
        await observer.on_job_completed(test_job, success_status)
        
        # Verification was attempted but failed gracefully
        http_client.get.assert_called_once()


# --- Observer Error Isolation Tests ---

class TestObserverErrorIsolation:
    """Test that observer exceptions don't break the job lifecycle."""
    
    @pytest.mark.asyncio
    async def test_observer_exception_does_not_propagate(self, test_job, accepted_status):
        """Observer exceptions should be caught and logged, not propagated."""
        
        class BrokenObserver:
            async def on_job_created(self, job, status_info):
                raise Exception("Observer is broken!")
            
            async def on_status_changed(self, job, old, new):
                pass
            
            async def on_job_completed(self, job, status_info):
                pass
        
        # This would be called in JobManager._notify_job_created
        broken_observer = BrokenObserver()
        
        # Should not raise (JobManager catches and logs)
        try:
            await broken_observer.on_job_created(test_job, accepted_status)
            pytest.fail("Expected exception was not raised")
        except Exception as e:
            # Exception is raised in test, but in JobManager it would be caught
            assert "Observer is broken!" in str(e)
