"""AI infrastructure layer for BB-PAXDATA.

This package contains the AI-related infrastructure components including
AI analysts, fail check systems, and other AI services that interface
with external AI providers (Ollama, Anthropic, Gemini, Groq).
"""

from .analyst import AIAnalyst
from .fail_check import AIFailCheck

__all__ = [
    "AIAnalyst",
    "AIFailCheck",
]
