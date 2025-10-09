# ump/core/managers/process_manager.py
from ump.core.interfaces.processes import ProcessesPort
from ump.core.interfaces.providers import ProvidersPort
from ump.core.interfaces.http_client import HttpClientPort
from ump.core.models.process import Process, ProcessList, ProcessSummary
from ump.core.models.providers_config import ProviderConfig
from ump.core.interfaces.process_id_validator import ProcessIdValidatorPort
import asyncio
from typing import List

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

    async def fetch_processes_for_provider(self, provider_name: str) -> List[ProcessSummary]:
        """
        Fetches the process list for a single provider asynchronously.
        Returns a list of Process objects for that provider.
        """
        provider: ProviderConfig = self.provider_config_service.get_provider(provider_name)
        url = str(provider.url).rstrip("/") + "/processes"
        try:
            # Fetch process metadata from remote provider
            data = await self.http_client.get(url, timeout=provider.timeout)
            processes = []
            for proc in data.get("processes", []):
                raw_proc_id = proc.get("id")
                try:
                    # Use validator to enforce process ID pattern
                    full_proc_id = self.process_id_validator.create(provider_name, raw_proc_id)
                    proc["id"] = full_proc_id
                    processes.append(ProcessSummary(**proc))
                except ValueError:
                    # Skip invalid process IDs
                    continue
            return processes
        except Exception as e:
            # On error, log and return empty list (could use cache here)
            # logger.error(f"Failed to fetch processes for provider {provider_name}: {e}")
            return []

    async def get_all_processes(self) -> ProcessList:
        """
        Fetches processes for all providers concurrently using asyncio.gather.
        Aggregates all results into a single ProcessList.
        """
        provider_names = self.provider_config_service.list_providers()
        # Create a coroutine for each provider
        tasks = [self.fetch_processes_for_provider(name) for name in provider_names]
        # Run all coroutines concurrently
        results = await asyncio.gather(*tasks)
        # Flatten the list of lists into a single list
        all_processes = [proc for sublist in results for proc in sublist]
        return ProcessList(processes=all_processes)

    async def cleanup(self) -> None:
        """Cleanup resources"""
        await self.http_client.close()
