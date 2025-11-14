"""Orchestrator for status derivation strategies.

Manages the chain of status derivation strategies and selects the appropriate
one based on the provider response pattern.
"""

from typing import List

from ump.core.interfaces.http_client import HttpClientPort
from ump.core.interfaces.status_derivation import (
    StatusDerivationStrategy,
    StatusDerivationContext,
    StatusDerivationResult,
)
from ump.core.managers.status_derivation_strategies import (
    DirectStatusInfoStrategy,
    ImmediateResultsStrategy,
    LocationFollowupStrategy,
    FallbackFailedStrategy,
)
from ump.core.settings import logger


class StatusDerivationOrchestrator:
    """Orchestrates status derivation using a chain of strategies.
    
    Evaluates provider responses against strategies in priority order:
    1. DirectStatusInfoStrategy - statusInfo present in body
    2. ImmediateResultsStrategy - outputs without statusInfo (sync execution)
    3. LocationFollowupStrategy - Location header only
    4. FallbackFailedStrategy - unparseable response (always matches)
    
    The first strategy that can handle the response is used.
    """
    
    def __init__(self, http_client: HttpClientPort):
        """Initialize orchestrator with ordered list of strategies.
        
        Args:
            http_client: HTTP client for strategies that need to make follow-up requests
        """
        self._strategies: List[StatusDerivationStrategy] = [
            DirectStatusInfoStrategy(http_client),
            ImmediateResultsStrategy(),
            LocationFollowupStrategy(http_client),
            FallbackFailedStrategy(),  # Catch-all, always at the end
        ]
    
    async def derive_status(
        self, context: StatusDerivationContext
    ) -> StatusDerivationResult:
        """Derive status information using the first matching strategy.
        
        Args:
            context: Provider response and job context
            
        Returns:
            StatusDerivationResult with derived status and metadata
        """
        for strategy in self._strategies:
            if strategy.can_handle(context):
                strategy_name = strategy.__class__.__name__
                logger.debug(
                    f"[orchestrator] using {strategy_name} for job_id={context.job.id}"
                )
                result = await strategy.derive(context)
                return result
        
        # Should never reach here since FallbackFailedStrategy always matches,
        # but provide a safety net
        logger.error(
            f"[orchestrator] no strategy matched job_id={context.job.id} (fallback should always match)"
        )
        fallback = FallbackFailedStrategy()
        return await fallback.derive(context)
