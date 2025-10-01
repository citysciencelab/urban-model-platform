from abc import ABC, abstractmethod
from typing import List, Dict, Any

class ConfigService(ABC):
    @abstractmethod
    def load_providers_config(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def validate_provider_config(self, config: Dict[str, Any]) -> bool:
        pass
