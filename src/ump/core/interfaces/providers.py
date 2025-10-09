# src/ump/core/services/provider_config_service.py

from abc import ABC, abstractmethod
from typing import List, Optional
from ump.core.models.providers_config import ProviderConfig, ProcessConfig

class ProvidersPort(ABC):
    @abstractmethod
    def load_providers(self) -> None:
        """Load or reload provider configurations from the source"""
        pass
    @abstractmethod
    def get_providers(self) -> List[ProviderConfig]:
        pass

    @abstractmethod
    def get_provider(self, provider_name: str) -> ProviderConfig:
        pass

    @abstractmethod
    def get_process_config(self, provider_name: str, process_id: str) -> ProcessConfig:
        pass

    @abstractmethod
    def list_providers(self) -> List[str]:
        pass

    @abstractmethod
    def get_processes(self, provider_name: str) -> List[str]:
        pass

    @abstractmethod
    def check_process_availability(self, provider_name: str, process_id: str) -> bool:
        pass
