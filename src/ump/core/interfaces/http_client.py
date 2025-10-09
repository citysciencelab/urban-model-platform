# ump/core/interfaces/http_client.py
from abc import ABC, abstractmethod
from typing import Any, Dict

class HttpClientPort(ABC):
    @abstractmethod
    async def get(self, url: str, timeout: float) -> Dict[str, Any]:
        """Make a GET request and return JSON response"""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close the HTTP client session"""
        pass
