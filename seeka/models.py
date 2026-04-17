import time
import uuid

from pydantic import BaseModel, Field


class Memo(BaseModel):
    """The atomic unit of memory in seeka."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="UUID auto-generated at creation")
    content: str = Field(description="A concise, self-contained memory statement")
    metadata: dict = Field(default_factory=dict, description="User-provided metadata")
    namespace: str = Field(default="", description="Memory namespace")


class Note(BaseModel):
    """A raw input record written by the developer, pending processing into Memos."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="UUID auto-generated at creation")
    content: str = Field(description="Raw input content")
    metadata: dict = Field(default_factory=dict, description="User-provided metadata")
    namespace: str = Field(default="", description="Memory namespace")
    status: str = Field(default="pending", description="pending / done / failed")
    created_at: int = Field(default_factory=lambda: int(time.time()), description="Unix timestamp")
