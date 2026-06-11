import hashlib
import re
import threading
from collections import OrderedDict
from typing import Any, Optional

from ...protocols import AppraisalServiceProtocol, BaseService
from ..lexicon.appraisal_config import get_appraisal_config
from ..lexicon.shared_lexicons import (
    GRADUATION_FORCE_DOWN,
    GRADUATION_FORCE_UP,
)
from ..models.appraisal_vector import (
    AffectType,
    AppraisalVector,
    AppreciationType,
    EngagementType,
    JudgmentType,
)
from ..models.srl import SRLFrame

# Lexicons sorted and prepared
AFFECT_LEXICON = {
    # Happiness
    "happy": (0.6, AffectType.HAPPINESS),
    "joyful": (0.8, AffectType.HAPPINESS),
    "welcomes": (0.5, AffectType.HAPPINESS),
    "welcome": (0.5, AffectType.HAPPINESS),
    "pleased": (0.6, AffectType.HAPPINESS),
    "delighted": (0.8, AffectType.HAPPINESS),
    "sad": (-0.6, AffectType.HAPPINESS),
    "grief": (-0.7, AffectType.HAPPINESS),
    "mourn": (-0.7, AffectType.HAPPINESS),
    "regret": (-0.5, AffectType.HAPPINESS),
    "unhappy": (-0.6, AffectType.HAPPINESS),
    # Security
    "safe": (0.7, AffectType.SECURITY),
    "secure": (0.7, AffectType.SECURITY),
    "confident": (0.6, AffectType.SECURITY),
    "trust": (0.7, AffectType.SECURITY),
    "peaceful": (0.6, AffectType.SECURITY),
    "deeply concerned": (-0.7, AffectType.SECURITY),
    "concerned": (-0.4, AffectType.SECURITY),
    "anxious": (-0.5, AffectType.SECURITY),
    "fear": (-0.6, AffectType.SECURITY),
    "threatened": (-0.6, AffectType.SECURITY),
    "threat": (-0.6, AffectType.SECURITY),
    "alarmed": (-0.5, AffectType.SECURITY),
    # Satisfaction
    "satisfied": (0.6, AffectType.SATISFACTION),
    "satisfaction": (0.6, AffectType.SATISFACTION),
    "pleasure": (0.5, AffectType.SATISFACTION),
    "angry": (-0.7, AffectType.SATISFACTION),
    "frustrated": (-0.6, AffectType.SATISFACTION),
    "frustration": (-0.6, AffectType.SATISFACTION),
    "displeased": (-0.6, AffectType.SATISFACTION),
}

JUDGMENT_LEXICON = {
    # Social Esteem
    "normal": (0.4, JudgmentType.ESTEEM, False),
    "competent": (0.7, JudgmentType.ESTEEM, False),
    "capable": (0.6, JudgmentType.ESTEEM, False),
    "determined": (0.7, JudgmentType.ESTEEM, False),
    "resolute": (0.7, JudgmentType.ESTEEM, False),
    "strong": (0.5, JudgmentType.ESTEEM, False),
    "brave": (0.7, JudgmentType.ESTEEM, False),
    "wise": (0.7, JudgmentType.ESTEEM, False),
    "intelligent": (0.6, JudgmentType.ESTEEM, False),
    "abnormal": (-0.5, JudgmentType.ESTEEM, False),
    "incompetent": (-0.7, JudgmentType.ESTEEM, False),
    "incapable": (-0.7, JudgmentType.ESTEEM, False),
    "weak": (-0.5, JudgmentType.ESTEEM, False),
    "cowardly": (-0.7, JudgmentType.ESTEEM, False),
    "foolish": (-0.6, JudgmentType.ESTEEM, False),
    "indecisive": (-0.6, JudgmentType.ESTEEM, False),
    # Social Sanction
    "honest": (0.7, JudgmentType.SANCTION, False),
    "truthful": (0.7, JudgmentType.SANCTION, False),
    "just": (0.7, JudgmentType.SANCTION, False),
    "fair": (0.6, JudgmentType.SANCTION, False),
    "proper": (0.5, JudgmentType.SANCTION, False),
    "right": (0.5, JudgmentType.SANCTION, False),
    "legal": (0.6, JudgmentType.SANCTION, False),
    "righteous": (0.7, JudgmentType.SANCTION, False),
    "dishonest": (-0.7, JudgmentType.SANCTION, False),
    "corrupt": (-0.8, JudgmentType.SANCTION, True),
    "unacceptable": (
        -0.7,
        JudgmentType.SANCTION,
        True,
    ),  # Keeps here, removed from appreciation
    "unjust": (-0.7, JudgmentType.SANCTION, True),
    "unfair": (-0.6, JudgmentType.SANCTION, True),
    "illegal": (-0.8, JudgmentType.SANCTION, True),
    "violates international law": (-0.9, JudgmentType.SANCTION, True),
    "violates": (-0.7, JudgmentType.SANCTION, True),
    "violation": (-0.7, JudgmentType.SANCTION, True),
    "criminal": (-0.8, JudgmentType.SANCTION, True),
    "immoral": (-0.8, JudgmentType.SANCTION, True),
    "evil": (-0.9, JudgmentType.SANCTION, True),
    "guilty": (-0.7, JudgmentType.SANCTION, True),
    "wrongful": (-0.6, JudgmentType.SANCTION, True),
    "unlawful": (-0.7, JudgmentType.SANCTION, True),
    "wicked": (-0.8, JudgmentType.SANCTION, True),
}

APPRECIATION_LEXICON = {
    # Reaction
    "interesting": (0.5, AppreciationType.REACTION),
    "engaging": (0.6, AppreciationType.REACTION),
    "beautiful": (0.7, AppreciationType.REACTION),
    "impressive": (0.7, AppreciationType.REACTION),
    "boring": (-0.5, AppreciationType.REACTION),
    "ugly": (-0.6, AppreciationType.REACTION),
    "dull": (-0.5, AppreciationType.REACTION),
    "monotonous": (-0.5, AppreciationType.REACTION),
    # Composition
    "balanced": (0.6, AppreciationType.COMPOSITION),
    "harmonious": (0.7, AppreciationType.COMPOSITION),
    "well-structured": (0.6, AppreciationType.COMPOSITION),
    "orderly": (0.5, AppreciationType.COMPOSITION),
    "unbalanced": (-0.6, AppreciationType.COMPOSITION),
    "chaotic": (-0.7, AppreciationType.COMPOSITION),
    "disorganized": (-0.6, AppreciationType.COMPOSITION),
    "confused": (-0.5, AppreciationType.COMPOSITION),
    # Value
    "valuable": (0.7, AppreciationType.VALUE),
    "important": (0.6, AppreciationType.VALUE),
    "significant": (0.6, AppreciationType.VALUE),
    "effective": (0.5, AppreciationType.VALUE),  # Keeps here, removed from judgment
    "meaningful": (0.6, AppreciationType.VALUE),
    "achievement": (0.7, AppreciationType.VALUE),
    "useless": (-0.7, AppreciationType.VALUE),
    "worthless": (-0.8, AppreciationType.VALUE),
    "insignificant": (-0.5, AppreciationType.VALUE),
}

# Sort longest first to avoid subphrase collision
_AFFECT_SORTED = sorted(AFFECT_LEXICON.items(), key=lambda x: len(x[0]), reverse=True)
_JUDGMENT_SORTED = sorted(
    JUDGMENT_LEXICON.items(), key=lambda x: len(x[0]), reverse=True
)
_APPRECIATION_SORTED = sorted(
    APPRECIATION_LEXICON.items(), key=lambda x: len(x[0]), reverse=True
)

# Precompile regex patterns
_AFFECT_PATTERNS = [
    (re.compile(rf"\b{re.escape(phrase)}\b", re.IGNORECASE), val)
    for phrase, val in _AFFECT_SORTED
]
_JUDGMENT_PATTERNS = [
    (re.compile(rf"\b{re.escape(phrase)}\b", re.IGNORECASE), val)
    for phrase, val in _JUDGMENT_SORTED
]
_APPRECIATION_PATTERNS = [
    (re.compile(rf"\b{re.escape(phrase)}\b", re.IGNORECASE), val)
    for phrase, val in _APPRECIATION_SORTED
]

_singleton_lock: threading.Lock = threading.Lock()


class AppraisalService(BaseService, AppraisalServiceProtocol):
    """Service for Martin & White (2005) Appraisal Vector analysis."""

    _instance: Optional["AppraisalService"] = None

    def __new__(cls, *args: Any, **kwargs: Any) -> "AppraisalService":
        if cls._instance is None:
            with _singleton_lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        super().__init__()
        self.config = get_appraisal_config()
        self._cache_max = self.config.cache_max_entries
        self._cache: OrderedDict[str, AppraisalVector] = OrderedDict()
        self._initialized = True

    def analyze(
        self,
        text: str,
        segment_id: str | None = None,
        srl_frame: SRLFrame | None = None,
        hedging_detected_markers: list[str] | None = None,
    ) -> AppraisalVector:
        """Analyze appraisal theory vectors in text, with LRU caching."""
        cache_key = self._cache_key(text, srl_frame, hedging_detected_markers)
        if cache_key in self._cache:
            # Move to end (LRU)
            vector = self._cache.pop(cache_key)
            self._cache[cache_key] = vector
            return vector

        # Compute
        vector = self._run_analysis(
            text, segment_id, srl_frame, hedging_detected_markers
        )

        # Cache store
        if len(self._cache) >= self._cache_max:
            self._cache.popitem(last=False)
        self._cache[cache_key] = vector

        return vector

    def _cache_key(
        self,
        text: str,
        srl_frame: SRLFrame | None,
        hedging_markers: list[str] | None,
    ) -> str:
        """Create a short SHA-256 hash representation key for caching."""
        text_norm = text.strip().lower()
        parts = [text_norm]
        if srl_frame:
            parts.append(f"srl:{srl_frame.argm_mod or ''}:{srl_frame.argm_neg}")
        if hedging_markers:
            parts.append(f"hedge:{','.join(sorted(hedging_markers))}")

        hasher = hashlib.sha256(":".join(parts).encode("utf-8"))
        return hasher.hexdigest()[:16]

    def _run_analysis(
        self,
        text: str,
        segment_id: str | None,
        srl_frame: SRLFrame | None,
        hedging_detected_markers: list[str] | None,
    ) -> AppraisalVector:
        """Perform lexicon matching and compute the Appraisal Vector."""
        text_lower = text.strip().lower()
        if not text_lower:
            return AppraisalVector(source_segment_id=segment_id)

        # Matched spans to prevent subphrase double-counting
        consumed_positions: list[tuple[int, int]] = []

        def is_span_consumed(start: int, end: int) -> bool:
            return any(start >= cs and end <= ce for cs, ce in consumed_positions)

        # 1. AFFECT detection
        affect_score = 0.0
        affect_type: AffectType | None = None
        affect_triggers: list[str] = []
        best_affect_score = 0.0

        for pattern, (score, aff_type) in _AFFECT_PATTERNS:
            for match in pattern.finditer(text_lower):
                start, end = match.start(), match.end()
                if is_span_consumed(start, end):
                    continue
                consumed_positions.append((start, end))
                affect_triggers.append(match.group(0))
                if abs(score) > abs(best_affect_score):
                    best_affect_score = score
                    affect_type = aff_type

        if best_affect_score != 0.0:
            affect_score = best_affect_score
        affect_confidence = (
            min(1.0, len(affect_triggers) * 0.3) if affect_triggers else 0.0
        )

        # 2. JUDGMENT detection
        judgment_score = 0.0
        judgment_type: JudgmentType | None = None
        judgment_is_sanction = False
        judgment_triggers: list[str] = []
        best_judgment_score = 0.0

        for pattern, (score, jud_type, is_sanc) in _JUDGMENT_PATTERNS:
            for match in pattern.finditer(text_lower):
                start, end = match.start(), match.end()
                if is_span_consumed(start, end):
                    continue
                consumed_positions.append((start, end))
                judgment_triggers.append(match.group(0))
                if abs(score) > abs(best_judgment_score):
                    best_judgment_score = score
                    judgment_type = jud_type
                    judgment_is_sanction = is_sanc

        if best_judgment_score != 0.0:
            judgment_score = best_judgment_score
        judgment_confidence = (
            min(1.0, len(judgment_triggers) * 0.3) if judgment_triggers else 0.0
        )

        # 3. APPRECIATION detection
        appreciation_score = 0.0
        appreciation_type: AppreciationType | None = None
        appreciation_triggers: list[str] = []
        best_appreciation_score = 0.0

        for pattern, (score, app_type) in _APPRECIATION_PATTERNS:
            for match in pattern.finditer(text_lower):
                start, end = match.start(), match.end()
                if is_span_consumed(start, end):
                    continue
                consumed_positions.append((start, end))
                appreciation_triggers.append(match.group(0))
                if abs(score) > abs(best_appreciation_score):
                    best_appreciation_score = score
                    appreciation_type = app_type

        if best_appreciation_score != 0.0:
            appreciation_score = best_appreciation_score
        appreciation_confidence = (
            min(1.0, len(appreciation_triggers) * 0.3) if appreciation_triggers else 0.0
        )

        # Collect all trigger words
        trigger_words = sorted(
            list(set(affect_triggers + judgment_triggers + appreciation_triggers))
        )

        # 4. GRADUATION detection
        graduation_force = 0.0
        graduation_force_direction: str | None = None

        force_up_hits = 0
        force_down_hits = 0

        for word in GRADUATION_FORCE_UP:
            pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
            matches = pattern.findall(text_lower)
            if matches:
                force_up_hits += len(matches)
                if word not in trigger_words:
                    trigger_words.append(word)

        for word in GRADUATION_FORCE_DOWN:
            pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
            matches = pattern.findall(text_lower)
            if matches:
                force_down_hits += len(matches)
                if word not in trigger_words:
                    trigger_words.append(word)

        # SRL Boost
        srl_boost = 0.0
        if srl_frame:
            modal = getattr(srl_frame, "argm_mod", None) or getattr(
                srl_frame, "argm_modal", None
            )
            if modal:
                modal_clean = modal.strip().lower()
                if modal_clean in [
                    "must",
                    "shall",
                    "should",
                    "will",
                    "definitely",
                    "certainly",
                ]:
                    srl_boost = self.config.srl_argm_mod_graduation_boost
                    graduation_force_direction = "up"
                elif modal_clean in ["might", "could", "may", "perhaps"]:
                    srl_boost = -0.1
                    graduation_force_direction = "down"

        if force_up_hits > 0 or force_down_hits > 0 or srl_boost != 0.0:
            raw_force = (force_up_hits * 0.25) - (force_down_hits * 0.15) + srl_boost
            graduation_force = max(0.0, min(1.0, abs(raw_force)))
            if raw_force >= 0:
                graduation_force_direction = "up"
            else:
                graduation_force_direction = "down"

        # 5. ENGAGEMENT detection
        hetero_hits = 0
        mono_hits = 0

        if hedging_detected_markers:
            hetero_hits += len(hedging_detected_markers)

        hetero_words = {
            "arguably",
            "perhaps",
            "maybe",
            "possibly",
            "probably",
            "suggests",
            "seems",
            "appears",
            "according to",
            "claims",
            "reports",
            "believed",
            "thought",
        }
        for word in hetero_words:
            pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
            if pattern.search(text_lower):
                hetero_hits += 1

        mono_words = {
            "must",
            "definitely",
            "absolutely",
            "shall",
            "always",
            "never",
            "certainly",
        }
        for word in mono_words:
            pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
            if pattern.search(text_lower):
                mono_hits += 1

        if hetero_hits > 0:
            engagement_type = EngagementType.HETEROGLOSS
            engagement_confidence = min(1.0, hetero_hits * 0.25)
        elif mono_hits > 0:
            engagement_type = EngagementType.MONOGLOSS
            engagement_confidence = min(1.0, mono_hits * 0.25)
        else:
            engagement_type = EngagementType.MONOGLOSS
            engagement_confidence = 0.0

        return AppraisalVector(
            affect_score=round(affect_score, 4),
            affect_type=affect_type,
            affect_confidence=round(affect_confidence, 4),
            judgment_score=round(judgment_score, 4),
            judgment_type=judgment_type,
            judgment_is_sanction=judgment_is_sanction,
            judgment_confidence=round(judgment_confidence, 4),
            appreciation_score=round(appreciation_score, 4),
            appreciation_type=appreciation_type,
            appreciation_confidence=round(appreciation_confidence, 4),
            graduation_force=round(graduation_force, 4),
            graduation_force_direction=graduation_force_direction,
            engagement_type=engagement_type,
            engagement_confidence=round(engagement_confidence, 4),
            source_segment_id=segment_id,
            trigger_words=sorted(list(set(trigger_words))),
        )


def get_appraisal_service() -> AppraisalService:
    """Return the global AppraisalService instance."""
    return AppraisalService()
