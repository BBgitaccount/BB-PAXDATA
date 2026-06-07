from enum import Enum
from typing import ClassVar, FrozenSet, Optional

from pydantic import BaseModel, Field


class SpeechActType(str, Enum):
    ASSERTIVE = "ASSERTIVE"
    DIRECTIVE = "DIRECTIVE"
    COMMISSIVE = "COMMISSIVE"
    EXPRESSIVE = "EXPRESSIVE"
    DECLARATIVE = "DECLARATIVE"
    INTERROGATIVE = "INTERROGATIVE"


class SpeechActClassification(BaseModel):
    """Represents a speech act classification with optional secondary type and confidence."""

    primary_type: SpeechActType
    secondary_type: Optional[SpeechActType] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    force_modifier: Optional[str] = None

    _COERCIVE_MODIFIERS: ClassVar[FrozenSet[str]] = frozenset(
        {
            "strongly",
            "categorically",
            "absolutely",
            "şiddetle",
            "kesinlikle",
            "kati",
            "mutlak",
        }
    )

    @property
    def is_coercive(self) -> bool:
        """Determines if the speech act represents a coercive directive."""
        return (
            self.primary_type == SpeechActType.DIRECTIVE
            and self.force_modifier is not None
            and self.force_modifier.lower() in self._COERCIVE_MODIFIERS
        )
