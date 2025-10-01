from pydantic import BaseModel, Field
from typing import List, Optional
from typing import Literal
from datetime import datetime

from ump.core.models.link import Link

class StatusCode(BaseModel):
    code: str  # Details je nach statusCode.yaml

class JobStatusInfo(BaseModel):
    jobID: str
    status: StatusCode
    type: Literal["process"] = "process"
    processID: Optional[str] = None
    message: Optional[str] = None
    created: Optional[datetime] = None
    started: Optional[datetime] = None
    finished: Optional[datetime] = None
    updated: Optional[datetime] = None
    progress: Optional[int] = Field(None, ge=0, le=100)
    links: Optional[List[Link]] = None

class JobList(BaseModel):
    jobs: List[JobStatusInfo]
    links: List[Link]
