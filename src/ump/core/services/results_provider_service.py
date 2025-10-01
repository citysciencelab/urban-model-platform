from abc import ABC, abstractmethod
from typing import Any, Dict

class ResultsProviderService(ABC):
    @abstractmethod
    def store_results(self, job_id: str, results: Any, config: Dict[str, Any]) -> Any:
        pass

    @abstractmethod
    def get_results_resource(self, job_id: str) -> Any:
        pass
