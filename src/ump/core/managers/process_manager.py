# ump/core/managers/process_manager.py
from ump.core.interfaces.processes import ProcessesPort
from ump.core.interfaces.providers import ProvidersPort
from ump.core.interfaces.http_client import HttpClientPort
from ump.core.models.process import Process, ProcessList

class ProcessManager(ProcessesPort):
    def __init__(
        self, 
        provider_config_service: ProvidersPort,
        http_client: HttpClientPort
    ) -> None:
        self.provider_config_service = provider_config_service
        self.http_client = http_client

    async def get_all_processes(self) -> ProcessList:
        all_processes = []

        for provider_name in self.provider_config_service.list_providers():
            provider = self.provider_config_service.get_provider(provider_name)
            url = str(provider.server_url).rstrip("/") + "/processes"
            
            data = await self.http_client.get(url, timeout=provider.timeout)
            
            for proc in data.get("processes", []):
                all_processes.append(Process(**proc))
        
        return ProcessList(processes=all_processes)
    
    async def cleanup(self) -> None:
        """Cleanup resources"""
        await self.http_client.close()
