from abc import ABC, abstractmethod
from typing import List, Dict, Any

class ProviderService(ABC):
    @abstractmethod
    def list_processes(self) -> List[Dict[str, Any]]:
        """
        Returns a list of available processes for this provider.
        """
        pass

    @abstractmethod
    def get_process(self, process_id: str) -> Dict[str, Any]:
        """
        Returns the details of the specified process.
        """
        pass

    @abstractmethod
    def start_job(self, process_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Starts a job for the given process with the provided parameters.
        """
        pass

    @abstractmethod
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Returns the status of the specified job.
        """
        pass

    @abstractmethod
    def get_job_results(self, job_id: str) -> Any:
        """
        Returns the results of the specified job.
        """
        pass
