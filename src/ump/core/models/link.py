from typing import Optional
from pydantic import BaseModel


class Link(BaseModel):
    href: str
    rel: str
    type: Optional[str] = None
    title: Optional[str] = None