from typing import List, Dict, Any
from ump.core.interfaces.provider_config import ProviderConfigPort
from ump.core.models.providers_config import ProcessConfig

class ProcessManager:
    def __init__(self, provider_config_service: ProviderConfigPort) -> None:
        self.provider_config_service = provider_config_service

    def list_all_processes(self) -> List[Dict[str, Any]]:
        processes: List[Dict[str, Any]] = []
        for provider_name in self.provider_config_service.list_providers():
            for process_id in self.provider_config_service.list_processes(provider_name):
                process_config: ProcessConfig = self.provider_config_service.get_process_config(provider_name, process_id)
                processes.append({
                    "provider": provider_name,
                    "process_id": process_id,
                    "config": process_config,
                })
        return processes
