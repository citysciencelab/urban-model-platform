from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any

from ump.core.models.link import Link


class JobControlOption(BaseModel):
    option: str  # Details je nach jobControlOptions.yaml

class TransmissionMode(BaseModel):
    mode: str  # Details je nach transmissionMode.yaml

class DescriptionType(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None

class ProcessSummary(DescriptionType):
    id: str
    version: str
    jobControlOptions: Optional[List[JobControlOption]] = None
    outputTransmission: Optional[List[TransmissionMode]] = None
    links: Optional[List[Link]] = None

class InputDescription(BaseModel):
    name: str
    schema: Any  # Details je nach inputDescription.yaml

class OutputDescription(BaseModel):
    name: str
    schema: Any  # Details je nach outputDescription.yaml

class Process(ProcessSummary):
    inputs: Optional[Dict[str, InputDescription]] = None
    outputs: Optional[Dict[str, OutputDescription]] = None
