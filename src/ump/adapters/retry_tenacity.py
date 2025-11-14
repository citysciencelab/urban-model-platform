from typing import Any, Awaitable, Callable, Sequence, Type
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential, retry_if_exception_type

class TenacityRetryAdapter:
    """Tenacity-based retry adapter implementing RetryPort.

    Provides exponential backoff and supports async callables. Call-time kwargs can
    override default policy parameters (attempts, wait_initial, wait_max, exception_types).
    """

    def __init__(
        self,
        attempts: int = 3,
        wait_initial: float = 0.2,
        wait_max: float = 1.0,
        exception_types: Sequence[Type[Exception]] = (Exception,),
    ) -> None:
        self.attempts = attempts
        self.wait_initial = wait_initial
        self.wait_max = wait_max
        self.exception_types = exception_types

    async def execute(self, func: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
        attempts = kwargs.pop("attempts", self.attempts)
        wait_initial = kwargs.pop("wait_initial", self.wait_initial)
        wait_max = kwargs.pop("wait_max", self.wait_max)
        exception_types = kwargs.pop("exception_types", self.exception_types)

        retrying = AsyncRetrying(
            stop=stop_after_attempt(attempts),
            wait=wait_exponential(multiplier=wait_initial, max=wait_max),
            retry=retry_if_exception_type(exception_types),
            reraise=True,
        )
        async for attempt in retrying:  # pragma: no cover - control flow instrumentation
            with attempt:
                return await func(*args, **kwargs)
