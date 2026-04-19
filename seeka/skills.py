"""
Built-in skill path constants for seeka's AgenticProcessor.

Usage:
    from seeka.skills import GENERAL, PREFERENCE

    mem = Memory(
        "./my_memory",
        llm_uri="bailian/qwen-plus",
        llm_api_key=api_key,
        skills=[GENERAL],                    # general memory extraction
        # skills=[GENERAL, PREFERENCE],      # with preference tracking
        # skills=["./my_domain_skill"],      # fully custom
        # skills=[GENERAL, "./my_skill"],    # built-in + custom mix
    )
"""
from seeka.processor.skills import GENERAL, PREFERENCE

__all__ = ["GENERAL", "PREFERENCE"]
