"""Protocol for status derivation strategies.

Defines the interface for different strategies that derive job status information
from provider responses, following the Strategy pattern.
"""

from typing import Protocol, Optional, Any, Dict
from ump.core.models.job import Job, JobStatusInfo


class StatusDerivationContext:
    """Context object containing all data needed for status derivation.
    
    Encapsulates provider response details and local job state to avoid
    passing many individual parameters to strategy methods.
    """
    
    def __init__(
        self,
        job: Job,
        process_id: str,
        provider: Any,
        provider_resp: Dict[str, Any],
        accepted_si: JobStatusInfo,
    ):
        self.job = job
        self.process_id = process_id
        self.provider = provider
        self.provider_resp = provider_resp
        self.accepted_si = accepted_si
        
        # Parsed provider response components
        self.provider_headers = provider_resp.get("headers", {})
        self.provider_body = provider_resp.get("body")
        self.provider_status = provider_resp.get("status")


class StatusDerivationResult:
    """Result of status derivation containing all extracted information.
    
    Attributes:
        status_info: Derived or synthesized job status information
        remote_status_url: URL for polling remote job status (if applicable)
        remote_job_id: Remote provider's job identifier (if different from local)
        diagnostic: Diagnostic message for troubleshooting (if any issues)
    """
    
    def __init__(
        self,
        status_info: JobStatusInfo,
        remote_status_url: Optional[str] = None,
        remote_job_id: Optional[str] = None,
        diagnostic: Optional[str] = None,
    ):
        self.status_info = status_info
        self.remote_status_url = remote_status_url
        self.remote_job_id = remote_job_id
        self.diagnostic = diagnostic


class StatusDerivationStrategy(Protocol):
    """Protocol defining the interface for status derivation strategies.
    
    Each strategy handles a specific provider response pattern:
    - DirectStatusInfoStrategy: statusInfo present in response body
    - ImmediateResultsStrategy: outputs present without statusInfo (synchronous execution)
    - LocationFollowupStrategy: Location header only, must follow to get status
    - FallbackFailedStrategy: unparseable response, create failed status
    """
    
    def can_handle(self, context: StatusDerivationContext) -> bool:
        """Check if this strategy can handle the given context.
        
        Args:
            context: Provider response and job context
            
        Returns:
            True if this strategy should be used for this response
        """
        ...
    
    async def derive(self, context: StatusDerivationContext) -> StatusDerivationResult:
        """Derive status information from provider response.
        
        Args:
            context: Provider response and job context
            
        Returns:
            StatusDerivationResult with derived status and metadata
        """
        ...
