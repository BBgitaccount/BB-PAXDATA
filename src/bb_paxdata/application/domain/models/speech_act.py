from enum import Enum
from typing import ClassVar, Final

from pydantic import BaseModel, Field

# Speech act dictionary keys for serialization/DB fields
SPEECH_ACT_PRIMARY: Final[str] = "speech_act_primary"
SPEECH_ACT_MODIFIER: Final[str] = "speech_act_modifier"
SPEECH_ACT_CONFIDENCE: Final[str] = "speech_act_confidence"


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
    secondary_type: SpeechActType | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    force_modifier: str | None = None

    _COERCIVE_MODIFIERS: ClassVar[frozenset[str]] = frozenset(
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
