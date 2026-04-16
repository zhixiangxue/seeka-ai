from pydantic import BaseModel, Field


class Memo(BaseModel):
    """The atomic unit of memory in seeka."""

    id: str = Field(default="", description="UUID assigned at storage time")
    content: str = Field(description="A concise, self-contained memory statement")
    metadata: dict = Field(default_factory=dict, description="User-provided metadata")
    namespace: str = Field(default="", description="Memory namespace")
