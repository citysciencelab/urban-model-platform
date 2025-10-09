# ump/core/managers/process_manager.py
from ump.core.interfaces.processes import ProcessesPort
from ump.core.interfaces.providers import ProvidersPort
from ump.core.interfaces.http_client import HttpClientPort
from ump.core.models.process import Process, ProcessList
from ump.core.models.providers_config import ProviderConfig
from ump.core.interfaces.process_id_validator import ProcessIdValidatorPort

class ProcessManager(ProcessesPort):
    def __init__(
        self, 
        provider_config_service: ProvidersPort,
        http_client: HttpClientPort,
        process_id_validator: ProcessIdValidatorPort
    ) -> None:
        self.provider_config_service = provider_config_service
        self.http_client = http_client
        self.process_id_validator = process_id_validator

    async def get_all_processes(self) -> ProcessList:
        all_processes = []

        for provider_name in self.provider_config_service.list_providers():
            
            provider: ProviderConfig = self.provider_config_service.get_provider(
                provider_name
            )
            url = str(provider.url).rstrip("/") + "/processes"
            
            data = await self.http_client.get(url, timeout=provider.timeout)
            
            for proc in data.get("processes", []):
                raw_proc_id = proc.get("id")
                try:
                    # Delegate pattern creation to the validator
                    full_proc_id = self.process_id_validator.create(provider_name, raw_proc_id)
                    proc["id"] = full_proc_id
                    
                    # TODO: Need to make sure domain in links are exchanged for UMP url
                    
                    all_processes.append(Process(**proc))
                except ValueError:
                    # Optionally log or skip invalid process IDs
                    continue
        
        return ProcessList(processes=all_processes)
    
    async def cleanup(self) -> None:
        """Cleanup resources"""
        await self.http_client.close()
