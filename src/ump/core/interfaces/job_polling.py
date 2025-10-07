from abc import ABC, abstractmethod
from typing import Dict, Any

class PollingService(ABC):
    @abstractmethod
    def poll_remote_job_status(self, job: Dict[str, Any]) -> str:
        pass
