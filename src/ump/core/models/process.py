from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from typing import List, Dict, Optional, Any, Union


from ump.core.models.link import Link
from ump.core.models.additional_parameter import AdditionalParameter


class ProcessJobControlOptions(str, Enum):
    SYNC_EXECUTE = "sync-execute"
    ASYNC_EXECUTE = "async-execute"
    DISMISS = "dismiss"

class ProcessOutputTransmission(str, Enum):
    VALUE = "value"
    REFERENCE = "reference"

class ResponseType(str, Enum):
    RAW = "raw"
    DOCUMENT = "document"

class Schema(BaseModel):
    type: Optional[str] = None
    format: Optional[str] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    minLength: Optional[int] = None
    maxLength: Optional[int] = None
    pattern: Optional[str] = None
    enum: Optional[List[Any]] = None
    properties: Optional[Dict[str, "Schema"]] = None
    required: Optional[List[str]] = None
    items: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = None
    oneOf: Optional[List[Dict[str, Any]]] = None
    allOf: Optional[List[Dict[str, Any]]] = None
    contentMediaType: Optional[str] = None
    contentEncoding: Optional[str] = None
    contentSchema: Optional[str] = None
    default: Optional[Any] = None

    class Config:
        exclude_none = True


class ProcessInput(BaseModel):
    title: str
    description: str
    scheme: Schema = Field(alias="schema")
    minOccurs: int = 1
    maxOccurs: Optional[int] = 1
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        exclude_none = True
        populate_by_name = True

class Metadata(BaseModel):
    title: str
    role: str
    href: str

class ProcessOutput(BaseModel):
    title: str
    description: str
    scheme: Schema = Field(alias="schema")
    metadata: List[Metadata] = []
    keywords: List[str] = []

    model_config = ConfigDict(
        populate_by_name=True,
    )

class DescriptionType(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[List[str]] = None
    metadata: Optional[List[Metadata]] = None
    additionalParameters: Optional[AdditionalParameter] = None

class ProcessSummary(DescriptionType):
    id: str
    version: str
    jobControlOptions: List[ProcessJobControlOptions]
    outputTransmission: List[ProcessOutputTransmission]
    links: List[Link]

    class Config:
        ignore_extra = True
        exclude_none = True
        populate_by_name = True

class Process(ProcessSummary):
    inputs: Optional[Dict[str, ProcessInput]] = None
    outputs: Optional[Dict[str, ProcessOutput]] = None

class ProcessList(BaseModel):
    processes: List[ProcessSummary]
    links: Optional[List[Link]] = None

