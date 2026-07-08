from importlib.metadata import version, PackageNotFoundError

from .memory import Memory, StorageBackend
from .models import Memo
from . import skills

try:
    __version__ = version("seeka")
except PackageNotFoundError:
    __version__ = "0.0.0.dev"

__all__ = ["Memory", "StorageBackend", "Memo", "skills", "__version__"]
