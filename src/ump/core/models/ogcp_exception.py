from pydantic import BaseModel
from typing import Optional


class AdditionalInfo(BaseModel):
    requestId: Optional[str] = None


class OGCExceptionResponse(BaseModel):
    type: str
    title: str
    status: int
    detail: str
    instance: Optional[str] = None
    additional: Optional[AdditionalInfo] = None

    def with_request_id(self, request_id: str) -> "OGCExceptionResponse":
        """Return copy that includes the given correlation/request id."""
        info = self.additional.model_copy() if self.additional else AdditionalInfo()
        info.requestId = request_id
        return self.model_copy(update={"additional": info})
