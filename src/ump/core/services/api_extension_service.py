from abc import ABC, abstractmethod
from typing import List, Dict, Any

class ApiExtensionService(ABC):
    @abstractmethod
    def list_extensions(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def execute_extension(self, extension_id: str, params: Dict[str, Any]) -> Any:
        pass

    @abstractmethod
    def get_extension_status(self, extension_id: str, params: Dict[str, Any]) -> str:
        pass

    @abstractmethod
    def list_extension_endpoints(self) -> List[str]:
        pass
