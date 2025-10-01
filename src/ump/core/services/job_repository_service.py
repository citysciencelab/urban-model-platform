from abc import ABC, abstractmethod
from typing import List, Dict, Any

class JobRepositoryService(ABC):
    @abstractmethod
    def save_job(self, job: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def get_job(self, job_id: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def list_jobs(self, user_id: str | None = None) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def update_job_status(self, job_id: str, status: str) -> None:
        pass

    @abstractmethod
    def delete_job(self, job_id: str) -> None:
        pass
