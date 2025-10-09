# ump/core/interfaces/processes.py
from abc import ABC, abstractmethod
from ump.core.models.process import ProcessList

class ProcessesPort(ABC):
    @abstractmethod
    async def get_all_processes(self) -> ProcessList:
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup resources"""
        pass