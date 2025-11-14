from typing import Protocol, Any, Awaitable, Callable

class RetryPort(Protocol):
    """Abstract retry interface for async operations.

    Implementations provide configurable retry with backoff for transient failures.
    The contract keeps the core decoupled from a specific library (tenacity/backoff).
    """
    async def execute(self, func: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:  # pragma: no cover - protocol
        """Execute an async callable with retry semantics.

        Args:
            func: Async callable returning a result.
            *args/**kwargs: Passed to the callable.
            Supported kw overrides (optional): attempts, wait_initial, wait_max, exception_types.
        Returns:
            Result of the successful invocation.
        Raises:
            Propagates last exception after exhausting attempts.
        """
        ...
