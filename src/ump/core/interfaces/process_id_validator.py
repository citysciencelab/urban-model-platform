from abc import ABC, abstractmethod

class ProcessIdValidatorPort(ABC):
    @abstractmethod
    def validate(self, process_id_with_prefix: str) -> bool:
        pass

    @abstractmethod
    def extract(self, process_id_with_prefix: str) -> tuple[str, str]:
        """
        Returns (provider_prefix, process_id) if valid, else raises ValueError.
        """
        pass

    @abstractmethod
    def create(self, provider_prefix: str, process_id: str) -> str:
        """
        Returns the full process id string in the enforced pattern.
        """
        pass
