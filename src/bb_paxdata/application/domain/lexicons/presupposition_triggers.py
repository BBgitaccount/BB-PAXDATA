"""
Language-aware presupposition trigger lexicon.
Supports English and Turkish triggers with lemma-based matching.
"""

from __future__ import annotations

from typing import ClassVar

from bb_paxdata.application.domain.models.presupposition import TriggerType


class PresuppositionLexicon:
    """
    Language-aware presupposition trigger lexicon.
    Default language: "en". Turkish ("tr") triggers are minimal
    and should be expanded in Phase 1.3.

    Uses lemma-based matching to handle morphological variants automatically.
    """

    _TRIGGERS: ClassVar[dict[str, dict[TriggerType, list[str]]]] = {
        "en": {
            TriggerType.FACTIVE_VERB: [
                "know",
                "realize",
                "notice",
                "regret",
                "forget",
                "remember",
                "acknowledge",
                "admit",
                "recognize",
                "appreciate",
                "understand",
                "see",
                "discover",
                "find",
                "observe",
            ],
            TriggerType.IMPLICATIVE_VERB: [
                "manage",
                "fail",
                "bother",
                "hesitate",
                "deign",
                "trouble",
                "condescend",
                "vouchsafe",
            ],
            TriggerType.TEMPORAL_ADVERB: [
                "still",
                "again",
                "already",
                "anymore",
                "yet",
            ],
            TriggerType.TEMPORAL_MULTIWORD: [
                "no longer",
            ],
            TriggerType.CHANGE_OF_STATE: [
                "stop",
                "start",
                "begin",
                "continue",
                "resume",
                "cease",
                "quit",
                "commence",
                "halt",
                "terminate",
            ],
            TriggerType.DEFINITE_NP: [
                # Definite articles and demonstratives are handled by spaCy DET tag
                # This list contains additional definite determiners
            ],
            TriggerType.CLEFT_CONSTRUCTION: [
                # Cleft patterns are structural, handled by dependency parse
                # "It was X that Y", "It is X who Y"
            ],
        },
        "tr": {
            TriggerType.FACTIVE_VERB: [
                "biliyor",
                "fark ediyor",
                "pişman",
                "hatırlıyor",
                "kabul ediyor",
                "anlıyor",
                "görüyor",
                "keşfediyor",
                "buluyor",
                "gözlemliyor",
            ],
            TriggerType.TEMPORAL_ADVERB: [
                "hâlâ",
                "yine",
                "artık",
                "zaten",
            ],
            TriggerType.CHANGE_OF_STATE: [
                "durdu",
                "başladı",
                "devam ediyor",
                "sürdürüyor",
                "yeniden başladı",
                "bıraktı",
            ],
        },
    }

    _MULTIWORD_PATTERNS: ClassVar[dict[str, list[str]]] = {
        "en": ["no longer"],
        "tr": [],
    }

    def __init__(self, language: str = "en") -> None:
        """
        Initialize lexicon for a specific language.

        Args:
            language: Language code ("en" or "tr")
        """
        self._language = language

    def get_triggers(self, trigger_type: TriggerType) -> list[str]:
        """
        Get trigger words for a specific type in the configured language.

        Args:
            trigger_type: Type of presupposition trigger

        Returns:
            List of trigger word lemmas
        """
        lang_triggers = self._TRIGGERS.get(self._language, self._TRIGGERS["en"])
        return lang_triggers.get(trigger_type, [])

    def get_all_triggers(self) -> dict[TriggerType, list[str]]:
        """
        Get all trigger types and their words for the configured language.

        Returns:
            Dictionary mapping trigger types to their word lists
        """
        return self._TRIGGERS.get(self._language, self._TRIGGERS["en"])

    def is_trigger(self, lemma: str, trigger_type: TriggerType) -> bool:
        """
        Check if a lemma is a trigger of a specific type.

        Args:
            lemma: Lemmatized word to check
            trigger_type: Type of presupposition trigger

        Returns:
            True if the lemma is a trigger of the given type
        """
        return lemma.lower() in self.get_triggers(trigger_type)

    def is_any_trigger(self, lemma: str) -> bool:
        """
        Check if a lemma is any type of presupposition trigger.

        Args:
            lemma: Lemmatized word to check

        Returns:
            True if the lemma is a trigger of any type
        """
        for trigger_type in TriggerType:
            if self.is_trigger(lemma, trigger_type):
                return True
        return False

    def get_trigger_type(self, lemma: str) -> TriggerType | None:
        """
        Get the trigger type for a lemma if it is a trigger.

        Args:
            lemma: Lemmatized word to check

        Returns:
            TriggerType if lemma is a trigger, None otherwise
        """
        for trigger_type in TriggerType:
            if self.is_trigger(lemma, trigger_type):
                return trigger_type
        return None

    def get_multiword_patterns(self) -> list[str]:
        """
        Get multiword trigger patterns for the configured language.

        Returns:
            List of multiword patterns (e.g., ["no longer"])
        """
        return self._MULTIWORD_PATTERNS.get(self._language, [])

    @classmethod
    def load_default(cls) -> PresuppositionLexicon:
        """
        Load default lexicon (English).

        Returns:
            PresuppositionLexicon instance with English triggers
        """
        return cls(language="en")

    @classmethod
    def for_language(cls, language: str) -> PresuppositionLexicon:
        """
        Load lexicon for a specific language.

        Args:
            language: Language code ("en" or "tr")

        Returns:
            PresuppositionLexicon instance for the specified language
        """
        return cls(language=language)
