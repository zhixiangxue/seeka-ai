"""
Built-in skill packs for seeka's AgenticProcessor.
Skills live here because they are processor configuration, not top-level package concepts.

Public access via the re-export layer:
    from seeka.skills import GENERAL, PREFERENCE
"""
from pathlib import Path

_DIR = Path(__file__).parent

# General-purpose memory extraction skill.
# Improves extraction quality: third-person perspective, time resolution,
# completeness over brevity, structured output.
GENERAL: str = str(_DIR / "general")

# Preference memory skill.
# Extracts and tracks explicit + implicit user preferences.
PREFERENCE: str = str(_DIR / "preference")

__all__ = ["GENERAL", "PREFERENCE"]
