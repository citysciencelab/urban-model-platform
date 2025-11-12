from pydantic import BaseModel
from typing import Optional, Dict, Any

class OGCExceptionResponse(BaseModel):
    type: str
    title: str
    status: int
    detail: str
    instance: Optional[str] = None
    additional: Optional[AdditionalInfo] = None


class AdditionalInfo(BaseModel):
    requestId: Optional[str] = None
