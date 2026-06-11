import re

import structlog

from bb_paxdata.application.domain.models.speech_act import (
    SpeechActClassification,
    SpeechActType,
)
from bb_paxdata.application.services.calibration_service import CalibrationService


class SpeechActClassifierService:
    """Service to classify speech acts based on heuristics and SRL context."""

    __slots__ = ("_calibration", "_log", "force_modifiers", "model_name", "triggers")

    def __init__(self, model_name: str = "deberta-v3-small") -> None:
        self.model_name = model_name
        self._log = structlog.get_logger(__name__).bind(service="speech_act_classifier")
        self._calibration = CalibrationService(metric="speech_act_confidence")

        # Compile regexes for Turkish and English force modifiers
        self.force_modifiers = {
            "strong": re.compile(
                r"\b(strongly|categorically|absolutely|firmly|mutlak|kati|şiddetle|kesinlikle)\b",
                re.IGNORECASE,
            ),
            "moderate": re.compile(
                r"\b(consistently|clearly|willingly|açıkça|düzenli|samimi)\b",
                re.IGNORECASE,
            ),
            "mitigated": re.compile(
                r"\b(respectfully|tentatively|humbly|saygıyla|ricayla|kısmen)\b",
                re.IGNORECASE,
            ),
        }

        # Compile regex triggers for speech act types
        self.triggers = {
            SpeechActType.DIRECTIVE: re.compile(
                r"\b(must|should|urge|demand|request|require|gerekir|zorunda|tavsiye|istiyoruz|talep|rica|emret)\b",
                re.IGNORECASE,
            ),
            SpeechActType.COMMISSIVE: re.compile(
                r"\b(will|shall|promise|guarantee|agree|commit|taahhüt|söz|kabul|anlaşma|yapacağız|edeceğiz)\b",
                re.IGNORECASE,
            ),
            SpeechActType.EXPRESSIVE: re.compile(
                r"\b(thank|congratulate|sorry|apologize|welcome|teşekkür|tebrik|üzgünüz|özür|hoşgeldin)\b",
                re.IGNORECASE,
            ),
            SpeechActType.DECLARATIVE: re.compile(
                r"\b(declare|announce|appoint|ilan|açıklıyorum|atıyorum|bildiriyorum)\b",
                re.IGNORECASE,
            ),
            SpeechActType.INTERROGATIVE: re.compile(
                r"\?|\b(what|how|why|who|when|where|neler|kim|nasıl|neden|halk|soruyorum)\b",
                re.IGNORECASE,
            ),
        }

    def classify_heuristically(self, text: str) -> SpeechActClassification:
        """Heuristically classifies speech acts and detects modifiers from text."""
        matched_types = []
        for sa_type, pattern in self.triggers.items():
            if pattern.search(text):
                matched_types.append(sa_type)

        # Sort matched types by priority
        priority = {
            SpeechActType.DIRECTIVE: 0,
            SpeechActType.COMMISSIVE: 1,
            SpeechActType.INTERROGATIVE: 2,
            SpeechActType.EXPRESSIVE: 3,
            SpeechActType.DECLARATIVE: 4,
            SpeechActType.ASSERTIVE: 5,
        }
        matched_types.sort(key=lambda t: priority.get(t, 5))

        primary = matched_types[0] if matched_types else SpeechActType.ASSERTIVE
        secondary = matched_types[1] if len(matched_types) > 1 else None

        # Detect force modifier
        detected_modifier = None
        for mod_name, pattern in self.force_modifiers.items():
            match = pattern.search(text)
            if match:
                detected_modifier = match.group(1).lower()
                break

        # Calculate base confidence
        raw_confidence = 0.75 if matched_types else 0.5
        calibrated = self._calibration.apply_platt_scaling(raw_confidence)

        return SpeechActClassification(
            primary_type=primary,
            secondary_type=secondary,
            confidence=round(calibrated, 3),
            force_modifier=detected_modifier,
        )

    async def classify(
        self, text: str, srl_context: dict | None = None
    ) -> SpeechActClassification:
        """Classifies speech act with optional SRL context validation."""
        if srl_context:
            # Check if SRL indicates a command/obligation modifier
            args = srl_context.get("args", [])
            mods = [a for a in args if a.get("role") == "ARGM-MOD"]
            if any(
                m.get("text", "").lower() in {"must", "should", "gerekir", "zorunda"}
                for m in mods
            ):
                heuristic = self.classify_heuristically(text)
                if heuristic.primary_type == SpeechActType.DIRECTIVE:
                    heuristic = heuristic.model_copy(
                        update={"confidence": min(1.0, heuristic.confidence + 0.15)}
                    )
                else:
                    # Upgrade to directive primary
                    old_primary = heuristic.primary_type
                    heuristic = heuristic.model_copy(
                        update={
                            "primary_type": SpeechActType.DIRECTIVE,
                            "secondary_type": (
                                old_primary
                                if old_primary != SpeechActType.DIRECTIVE
                                else None
                            ),
                            "confidence": min(1.0, heuristic.confidence + 0.15),
                        }
                    )
                return heuristic

        return self.classify_heuristically(text)
