"""OGC API Processes Execute request models (simplified).

Derived from execute.yaml and related schema fragments.
We intentionally simplify some nested schema details while preserving
structural intent:
- inputs: map<string, InlineOrRef | [InlineOrRef,...]>
- outputs: map<string, OutputSpec>
- response: 'raw' | 'document' (default 'raw')
- subscriber: optional callback URIs (if conformance class implemented)

InlineOrRef covers:
 - direct scalar/object value (value/data)
 - qualified value with format metadata
 - link reference (href)

This model normalizes inputs so downstream code can treat each entry as:
    { "id": key, "values": [ InlineOrRef, ... ] }
Without losing ability to reference remote resources.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import (
    BaseModel,
    Field,
    HttpUrl,
    computed_field,
    field_validator,
    model_validator,
)


class ResponseMode(str, Enum):
    raw = "raw"
    document = "document"


class TransmissionMode(str, Enum):
    inline = "value"  # inline result value
    reference = "reference"  # remote URL reference


class InlineOrRef(BaseModel):
    """Represents either inline data or a reference link.

    We collapse multiple OGC schema oneOf choices into a single flexible model.
    """

    value: Any | None = Field(None, description="Inline value (scalar/object/array)")
    href: Optional[HttpUrl] = Field(None, description="External reference URL")
    format: Optional[str] = Field(None, description="Media type or format identifier")

    @computed_field
    @property
    def is_reference(self) -> bool:
        return self.href is not None and self.value is None

    @computed_field
    @property
    def is_inline(self) -> bool:
        return self.value is not None

    @model_validator(mode="after")
    def ensure_value_or_href(self):
        if self.value is None and self.href is None:
            raise ValueError("InlineOrRef requires either 'value' or 'href'.")
        return self


class OutputSpec(BaseModel):
    format: Optional[str] = Field(
        None, description="Requested output format / media type"
    )
    transmissionMode: Optional[TransmissionMode] = Field(
        None, description="inline (value) or reference"
    )


class SubscriberCallbacks(BaseModel):
    successUri: HttpUrl
    inProgressUri: Optional[HttpUrl] = None
    failedUri: Optional[HttpUrl] = None


class NormalizedInput(BaseModel):
    id: str
    values: List[InlineOrRef]


class ExecuteRequest(BaseModel):
    inputs: Dict[str, Union[InlineOrRef, List[InlineOrRef]]] = Field(
        default_factory=dict,
        description="Map of input identifier to one or more inline/reference values",
    )
    outputs: Optional[Dict[str, OutputSpec]] = None
    response: ResponseMode = ResponseMode.raw
    subscriber: Optional[SubscriberCallbacks] = None

    @field_validator("inputs")
    def validate_inputs(cls, v):
        # Basic structural validation: ensure each value is InlineOrRef or list thereof.
        for key, val in v.items():
            if isinstance(val, list):
                if not val:
                    raise ValueError(f"Input '{key}' list must not be empty")
                for item in val:
                    if not isinstance(item, InlineOrRef):
                        raise ValueError(
                            f"Input '{key}' list contains non InlineOrRef item"
                        )
            elif not isinstance(val, InlineOrRef):
                raise ValueError(
                    f"Input '{key}' must be InlineOrRef or list[InlineOrRef]"
                )
        return v

    def normalized_inputs(self) -> List[NormalizedInput]:
        result: List[NormalizedInput] = []
        for key, val in self.inputs.items():
            if isinstance(val, list):
                result.append(NormalizedInput(id=key, values=val))
            else:
                result.append(NormalizedInput(id=key, values=[val]))
        return result

    def as_provider_payload(self) -> Dict[str, Any]:
        """Convert to provider-friendly payload structure.

        For simplicity we keep the original mapping but flatten lists where single entry.
        """
        inputs_payload: Dict[str, Any] = {}
        for key, val in self.inputs.items():
            if isinstance(val, list):
                # provider may expect array or first value; we retain list of either value/href dicts
                inputs_payload[key] = [
                    item.value if item.is_inline else {"href": str(item.href)}
                    for item in val
                ]
            else:
                inputs_payload[key] = (
                    val.value if val.is_inline else {"href": str(val.href)}
                )
        payload: Dict[str, Any] = {"inputs": inputs_payload}
        if self.outputs:
            payload["outputs"] = {
                k: {k2: v2 for k2, v2 in spec.model_dump(exclude_none=True).items()}
                for k, spec in self.outputs.items()
            }
        payload["response"] = self.response.value
        if self.subscriber:
            payload["subscriber"] = self.subscriber.model_dump(exclude_none=True)
        return payload
