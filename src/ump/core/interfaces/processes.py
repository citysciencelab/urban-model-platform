from abc import ABC, abstractmethod
from ump.core.models.process import ProcessList

class ProcessesPort(ABC):
    @abstractmethod
    def get_all_processes(self) -> ProcessList:
        pass
