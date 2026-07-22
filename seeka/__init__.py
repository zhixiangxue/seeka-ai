from importlib.metadata import version, PackageNotFoundError

from .memory import Memory, VectorDB, GraphDB
from .models import Memo, Note, Entity, Triple
from . import skills

try:
    __version__ = version("seeka")
except PackageNotFoundError:
    __version__ = "0.0.0.dev"

__all__ = ["Memory", "VectorDB", "GraphDB", "Memo", "Note", "Entity", "Triple", "skills", "__version__"]
