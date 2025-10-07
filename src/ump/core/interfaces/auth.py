from abc import ABC, abstractmethod
from typing import Any, Dict

class AuthService(ABC):
    @abstractmethod
    def verify_jwt(self, token: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def authorize_access(self, user: Dict[str, Any], resource_id: str, resource_type: str) -> bool:
        pass

    @abstractmethod
    def fetch_kids(self) -> list:
        pass
