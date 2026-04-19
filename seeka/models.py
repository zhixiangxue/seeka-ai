import json
import time

from nanoid import generate as nanoid
from pydantic import BaseModel, Field, field_validator


def _parse_metadata(v: object) -> dict:
    """Ensure metadata is always a dict. Accepts dict or JSON string."""
    if isinstance(v, dict):
        return v
    if isinstance(v, str):
        try:
            parsed = json.loads(v)
        except json.JSONDecodeError as e:
            raise ValueError(f"metadata must be a dict or valid JSON string, got: {v!r}") from e
        if not isinstance(parsed, dict):
            raise ValueError(f"metadata JSON must decode to a dict, got {type(parsed).__name__}")
        return parsed
    if v is None:
        return {}
    raise ValueError(f"metadata must be a dict, got {type(v).__name__}")


class Memo(BaseModel):
    """The atomic unit of memory in seeka."""

    id: str = Field(default_factory=nanoid, description="nanoid auto-generated at creation")
    content: str = Field(description="A concise, self-contained memory statement")
    metadata: dict = Field(default_factory=dict, description="User-provided metadata")
    namespace: str = Field(default="", description="Memory namespace")
    created: int = Field(default_factory=lambda: int(time.time()), description="Unix timestamp of when this Memo was created")
    modified: int | None = Field(default=None, description="Unix timestamp of the last update, None if never modified")
    embedding: list[float] | None = Field(default=None, exclude=True, description="Vector embedding, set at write time, not persisted to archive")

    @field_validator("metadata", mode="before")
    @classmethod
    def _coerce_metadata(cls, v: object) -> dict:
        return _parse_metadata(v)


class Note(BaseModel):
    """A raw input record written by the developer, pending processing into Memos."""

    id: str = Field(default_factory=nanoid, description="nanoid auto-generated at creation")
    content: str = Field(description="Raw input content")
    metadata: dict = Field(default_factory=dict, description="User-provided metadata")
    namespace: str = Field(default="", description="Memory namespace")
    status: str = Field(default="pending", description="pending / done / failed")
    created: int = Field(default_factory=lambda: int(time.time()), description="Unix timestamp")

    @field_validator("metadata", mode="before")
    @classmethod
    def _coerce_metadata(cls, v: object) -> dict:
        return _parse_metadata(v)
