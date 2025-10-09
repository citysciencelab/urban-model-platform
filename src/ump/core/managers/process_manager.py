import httpx
from ump.core.interfaces.processes import ProcessesPort
from ump.core.interfaces.providers import ProvidersPort
from ump.core.models.process import Process, ProcessList

class ProcessManager(ProcessesPort):
    def __init__(self, provider_config_service: ProvidersPort) -> None:
        self.provider_config_service = provider_config_service

    def get_all_processes(self) -> ProcessList:

        all_processes = []

        for provider_name in self.provider_config_service.list_providers():
            
            provider = self.provider_config_service.get_provider(provider_name)
            
            url = str(provider.server_url).rstrip("/") + "/processes"
            
            response = httpx.get(url, timeout=provider.timeout)
            
            response.raise_for_status()
            
            data = response.json()
            
            for proc in data.get("processes", []):
                all_processes.append(Process(**proc))
        
        return ProcessList(processes=all_processes)