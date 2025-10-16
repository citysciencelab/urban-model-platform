from abc import ABC, abstractmethod
from typing import Dict, Any


class SiteInfoPort(ABC):
    @abstractmethod
    def get_site_info(self) -> Dict[str, Any]:
        """Return a serializable mapping with site metadata for the landing page."""
        pass
