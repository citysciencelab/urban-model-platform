import time
from typing import List, Dict, TypeVar, Generic, Optional

T = TypeVar('T')

class ProcessListCache(Generic[T]):
    def __init__(self, expiry_seconds: int = 300):
        self._cache: Dict[str, tuple[float, List[T]]] = {}
        self._expiry_seconds = expiry_seconds

    def get(self, key: str) -> Optional[List[T]]:
        entry = self._cache.get(key)
        if entry:
            timestamp, value = entry
            if time.time() - timestamp < self._expiry_seconds:
                return value
        return None

    def set(self, key: str, value: List[T]):
        self._cache[key] = (time.time(), value)
