"""Configuration models for core domain components.

This module provides Pydantic-based configuration classes that consolidate
settings for domain managers, enabling dependency injection and testability.
"""

from typing import Optional
from pydantic import BaseModel, Field


class JobManagerConfig(BaseModel):
    """Configuration for JobManager behavior.
    
    Consolidates all job execution settings in one place, enabling:
    - Clear dependency injection in composition roots
    - Easy testing with custom configurations
    - Type-safe access to settings
    - Self-documenting configuration
    
    Attributes:
        poll_interval: Seconds between remote status poll requests (float for test flexibility)
        poll_timeout: Maximum seconds to wait for job completion (None = no timeout)
        rewrite_remote_links: Whether to replace remote links with local equivalents
        inline_inputs_size_limit: Maximum size (bytes) for storing inputs inline vs object storage
    """
    
    poll_interval: float = Field(
        default=5.0,
        gt=0,
        description="Interval in seconds between remote job status polling requests"
    )
    
    poll_timeout: Optional[float] = Field(
        default=None,
        gt=0,
        description="Maximum time in seconds to wait for remote job completion (None for no timeout)"
    )
    
    rewrite_remote_links: bool = Field(
        default=True,
        description="Replace external provider links with local API links in responses"
    )
    
    inline_inputs_size_limit: int = Field(
        default=64 * 1024,  # 64 KB
        ge=0,
        description="Maximum size in bytes for storing job inputs inline (larger inputs use object storage)"
    )
    
    forward_max_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum retry attempts for transient errors when forwarding to remote provider"
    )
    
    forward_retry_base_wait: float = Field(
        default=1.0,
        gt=0,
        description="Base wait time in seconds for exponential backoff between retries"
    )
    
    forward_retry_max_wait: float = Field(
        default=5.0,
        gt=0,
        description="Maximum wait time in seconds between retry attempts"
    )
    
    model_config = {
        "frozen": True,  # Immutable after creation for safety
        "extra": "forbid",  # Reject unknown fields
    }
    
    @classmethod
    def from_app_settings(cls, settings) -> "JobManagerConfig":
        """Factory method to construct config from UmpSettings instance.
        
        Args:
            settings: UmpSettings instance from core.settings
            
        Returns:
            JobManagerConfig with values from app settings
        """
        return cls(
            poll_interval=settings.UMP_REMOTE_JOB_STATUS_REQUEST_INTERVAL,
            poll_timeout=settings.UMP_REMOTE_JOB_TTW,
            rewrite_remote_links=settings.UMP_REWRITE_REMOTE_LINKS,
            # inline_inputs_size_limit, forward_max_retries, forward_retry_base_wait, 
            # forward_retry_max_wait all use defaults (no settings exist yet)
        )
