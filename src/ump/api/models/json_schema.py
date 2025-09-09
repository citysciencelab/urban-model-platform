import re
from typing import Any, Dict, List, Optional, Union, Any

from pydantic import BaseModel, Field, field_validator


class Reference(BaseModel):
    ref: str = Field(..., alias="$ref")

    @field_validator("ref")
    def validate_uri_reference(cls, v):
        # Basic URI reference regex (RFC 3986, not exhaustive)
        uri_ref_regex = r"^[A-Za-z0-9+.-]+:(//)?[^\s]*$"
        if not re.match(uri_ref_regex, v):
            raise ValueError("'$ref' must be a valid URI reference")
        return v


class JSONSchema(BaseModel):
    # Basic fields
    title: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = Field(None)
    format: Optional[str] = None
    contentMediaType: Optional[str] = None
    contentEncoding: Optional[str] = None
    contentSchema: Optional[str] = None
    default: Optional[Any] = None
    nullable: Optional[bool] = None
    readOnly: Optional[bool] = None
    writeOnly: Optional[bool] = None
    example: Optional[Any] = None
    deprecated: Optional[bool] = None

    # Numeric constraints
    multipleOf: Optional[float] = None
    maximum: Optional[float] = None
    exclusiveMaximum: Optional[bool] = None
    minimum: Optional[float] = None
    exclusiveMinimum: Optional[bool] = None

    # String constraints
    maxLength: Optional[int] = None
    minLength: Optional[int] = None
    pattern: Optional[str] = None

    # Array constraints
    maxItems: Optional[int] = None
    minItems: Optional[int] = None
    uniqueItems: Optional[bool] = None

    # Object constraints
    maxProperties: Optional[int] = None
    minProperties: Optional[int] = None

    # Required and enum
    required: Optional[List[str]] = None
    enum: Optional[List[Any]] = None

    # Composite keywords
    not_: Optional[Union["JSONSchema", Reference]] = Field(None, alias="not")
    allOf: Optional[List[Union["JSONSchema", Reference]]] = None
    oneOf: Optional[List[Union["JSONSchema", Reference]]] = None
    anyOf: Optional[List[Union["JSONSchema", Reference]]] = None

    # Items and properties
    items: Optional[Union["JSONSchema", Reference]] = None
    properties: Optional[Dict[str, Union["JSONSchema", Reference]]] = None
    additionalProperties: Optional[Union["JSONSchema", Reference, bool]] = None

    # Allow for arbitrary extra fields
    extra: Dict[str, Any] = {}

    class Config:
        extra = "allow"
        allow_population_by_field_name = True


# Allowed content encoding values (extend as needed)
ALLOWED_CONTENT_ENCODINGS = ["base64", "gzip", "deflate", "identity"]

# Common content media types (extend as needed)
ALLOWED_CONTENT_MEDIA_TYPES = [
    "application/json",
    "application/gzip",
    "application/zip",
    "text/csv",
    "image/tiff",
    "image/tiff; application=geotiff",
    "application/pdf",
    "application/xml",
    "text/plain",
]


class Metadata(BaseModel):
    title: Optional[str] = None
    role: Optional[str] = None
    href: Optional[str] = None


class AdditionalParameter(BaseModel):
    name: str
    value: List[Any]


class AdditionalParameters(BaseModel):
    parameters: Optional[List[AdditionalParameter]] = None


class DescriptionType(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[List[str]] = None
    metadata: Optional[List[Metadata]] = None
    additionalParameters: Optional[AdditionalParameters] = None


class ProcessInput(DescriptionType):
    minOccurs: Optional[int] = 1
    maxOccurs: Optional[Union[int, str]] = 1
    schema: JSONSchema


class ProcessOutput(DescriptionType):
    schema: JSONSchema


JSONSchema.model_rebuild()

