from __future__ import annotations

import math
import re

import structlog

logger = structlog.get_logger(__name__)

ENGAGEMENT_MARKERS = {
    "attribution": ["according to", "claims that", "states", "argues", "reports"],
    "concession": ["although", "even though", "despite", "while", "granted"],
    "countering": ["but", "however", "yet", "on the contrary", "nevertheless"],
    "modality": ["may", "might", "could", "perhaps", "possibly"],
}

GRADUATION_FORCE = {
    "boosters": ["clearly", "certainly", "definitely", "highly", "very"],
    "hedges": ["somewhat", "partly", "roughly", "around", "about"],
}

STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "if",
    "because",
    "as",
    "what",
    "which",
    "this",
    "that",
    "these",
    "those",
    "then",
    "just",
    "so",
    "than",
    "such",
    "ve",
    "veya",
    "ama",
    "fakat",
    "lakin",
    "ise",
    "ki",
    "da",
    "de",
    "mu",
    "mı",
    "bu",
    "şu",
    "o",
    "bir",
    "için",
    "ile",
    "en",
    "daha",
    "kadar",
    "gibi",
}

DEMAND_KEYWORDS = {
    "must",
    "should",
    "demand",
    "require",
    "insist",
    "urge",
    "request",
    "need to",
    "gerekmek",
    "zorunlu",
    "talep etmek",
    "istemek",
    "çağrıda bulunmak",
    "lazım",
    "meli",
    "malı",
    "edeceğiz",
    "istiyoruz",
    "bekliyoruz",
}

RST_CONNECTIVES = {
    "because",
    "although",
    "however",
    "therefore",
    "since",
    "moreover",
    "nevertheless",
    "consequently",
    "whereas",
    "nonetheless",
    "furthermore",
    "çünkü",
    "rağmen",
    "ancak",
    "ama",
    "fakat",
    "dolayısıyla",
    "bu yüzden",
    "ayrıca",
    "bununla birlikte",
    "nitekim",
    "zira",
    "bundan dolayı",
}

SUBORDINATORS = {
    "although",
    "even though",
    "though",
    "because",
    "since",
    "if",
    "eğer",
    "çünkü",
    "rağmen",
    "ise",
}

ELABORATION_CONNECTIVES = {
    "furthermore",
    "moreover",
    "in addition",
    "additionally",
    "ayrıca",
    "ek olarak",
    "hem de",
    "bununla birlikte",
    "bunun yanında",
}

EVASION_MARKERS = {
    "[...]",
    "...",
    "no comment",
    "decline to answer",
    "off the record",
    "yorum yok",
    "cevap yok",
    "kayıt dışı",
    "açıklama yapamam",
    "sessiz",
    "no response",
    "decline to comment",
}


ME_MA_LI_LI_PATTERN = re.compile(
    r"\b\w+(?:meli|malı)(?:yim|yım|sin|sın|yiz|yız|siniz|sınız|ler|lar|ydi|ydı|ymış|ymış|yse|ysek|n|m|k)?\b"
)


def _match_engagement_marker(sent_lower: str, marker: str) -> bool:
    if marker == "states":
        return bool(re.search(r"\b(?<!united\s)states\b", sent_lower))
    elif marker == "yet":
        return bool(re.search(r"\byet\b", sent_lower))
    else:
        return bool(re.search(rf"\b{re.escape(marker)}\b", sent_lower))


def _match_word(sent_lower: str, word: str) -> bool:
    return bool(re.search(rf"\b{re.escape(word)}\b", sent_lower))


def _match_demand_keyword(sent_lower: str, keyword: str) -> bool:
    if keyword in ("meli", "malı"):
        return bool(ME_MA_LI_LI_PATTERN.search(sent_lower))
    if keyword in (
        "demand",
        "require",
        "insist",
        "urge",
        "request",
        "gerekmek",
        "istemek",
    ):
        return bool(re.search(rf"\b{re.escape(keyword)}\w*\b", sent_lower))
    if keyword == "talep etmek":
        return bool(re.search(r"\btalep\s+etmek\w*\b", sent_lower))
    if keyword == "çağrıda bulunmak":
        return bool(re.search(r"\bçağrıda\s+bulunmak\w*\b", sent_lower))
    return bool(re.search(rf"\b{re.escape(keyword)}\b", sent_lower))


def _match_rst_connective(sent_lower: str, conn: str) -> bool:
    return bool(re.search(rf"\b{re.escape(conn)}\b", sent_lower))


def _count_elaboration_connective(sent_lower: str, conn: str) -> int:
    return len(re.findall(rf"\b{re.escape(conn)}\b", sent_lower))


def _count_evasion_marker(sent_lower: str, ev_marker: str) -> int:
    if ev_marker in ("...", "[...]"):
        return sent_lower.count(ev_marker)
    return len(re.findall(rf"\b{re.escape(ev_marker)}\b", sent_lower))


class DetailedEngagementScore(float):
    """Float subclass that carries additional engagement/rhetorical metadata."""

    velocity: float
    density: float
    referential_cohesion: float
    rst_depth: float
    nucleus_ratio: float
    elaboration_density: float
    silence_density: float
    evasion_flag: bool
    pressure_index: float
    intervention_timing_cv: float

    def __new__(
        cls,
        value: float,
        velocity: float,
        density: float,
        referential_cohesion: float,
        rst_depth: float,
        nucleus_ratio: float,
        elaboration_density: float,
        silence_density: float,
        evasion_flag: bool,
        pressure_index: float,
        intervention_timing_cv: float,
    ) -> DetailedEngagementScore:
        obj = super().__new__(cls, value)
        obj.velocity = velocity
        obj.density = density
        obj.referential_cohesion = referential_cohesion
        obj.rst_depth = rst_depth
        obj.nucleus_ratio = nucleus_ratio
        obj.elaboration_density = elaboration_density
        obj.silence_density = silence_density
        obj.evasion_flag = evasion_flag
        obj.pressure_index = pressure_index
        obj.intervention_timing_cv = intervention_timing_cv
        return obj


class EngagementAnalyzer:
    """
    Implements Martin & White (2005) Appraisal Theory Engagement analysis
    along with advanced rhetorical structure and discursive velocity metrics.

    Academic Source:
    Martin, J. R., & White, P. R. (2005). The language of evaluation:
    Appraisal in English. Palgrave Macmillan.
    """

    def __init__(self) -> None:
        self.markers = ENGAGEMENT_MARKERS
        self.graduation = GRADUATION_FORCE

    async def score(
        self,
        sentences: list[str],
        speaker_id: str,
        timestamps: list[float] | None = None,
        speaker_timestamps: list[float] | None = None,
    ) -> DetailedEngagementScore:
        """
        Return engagement score ∈ [0, 1].
        Formula: (polygloss_count / total_engagement_markers) × avg(graduation_force)
        Also computes advanced metrics for discourse structure, velocity, silence, and RST depth.
        """
        if not sentences:
            return DetailedEngagementScore(
                0.0,
                velocity=0.0,
                density=0.0,
                referential_cohesion=0.0,
                rst_depth=1.0,
                nucleus_ratio=0.0,
                elaboration_density=0.0,
                silence_density=0.0,
                evasion_flag=False,
                pressure_index=0.0,
                intervention_timing_cv=0.0,
            )

        polygloss_count = 0
        total_markers = 0
        force_scores = []
        demands_count = 0
        silence_markers_count = 0

        # Heuristic content words function for cohesion
        def get_content_words(text_str: str) -> set[str]:
            words = re.findall(r"\b\w+\b", text_str.lower())
            return {w for w in words if w not in STOPWORDS and len(w) > 2}

        # 1. Discourse Velocity & Density (B2)
        # 2. RST (Rhetorical Structure Theory) (A9)
        # 3. Diplomatik Sessizlik (B6)
        nucleus_count = 0
        depth_scores = []
        elaboration_count = 0

        for sent in sentences:
            sent_lower = sent.lower()
            is_polygloss = False

            # Check for polygloss markers
            for category, markers in self.markers.items():
                for marker in markers:
                    if _match_engagement_marker(sent_lower, marker):
                        is_polygloss = True
                        total_markers += 1

            if is_polygloss:
                polygloss_count += 1

            # Check for graduation force
            for booster in self.graduation["boosters"]:
                if _match_word(sent_lower, booster):
                    force_scores.append(1.0)
            for hedge in self.graduation["hedges"]:
                if _match_word(sent_lower, hedge):
                    force_scores.append(0.5)

            # Demands count for density
            if any(
                _match_demand_keyword(sent_lower, demand_kw)
                for demand_kw in DEMAND_KEYWORDS
            ):
                demands_count += 1

            # Silence / evasion markers
            for ev_marker in EVASION_MARKERS:
                silence_markers_count += _count_evasion_marker(sent_lower, ev_marker)

            # RST depth heuristic: 1 + count of connectives
            depth = 1.0 + sum(
                1.0
                for conn in RST_CONNECTIVES
                if _match_rst_connective(sent_lower, conn)
            )
            depth_scores.append(depth)

            # RST nucleus ratio heuristic
            tokens = sent_lower.split()
            if tokens and tokens[0] in SUBORDINATORS:
                pass
            else:
                nucleus_count += 1

            # RST elaboration density heuristic
            for conn in ELABORATION_CONNECTIVES:
                elaboration_count += _count_elaboration_connective(sent_lower, conn)

        # Baseline engagement score
        if total_markers == 0:
            base_score = 0.0
        else:
            avg_force = sum(force_scores) / len(force_scores) if force_scores else 0.75
            base_score = min(
                max((polygloss_count / total_markers) * avg_force, 0.0), 1.0
            )

        # Discourse velocity
        if timestamps and len(timestamps) >= 2:
            dt = max(timestamps) - min(timestamps)
            velocity = polygloss_count / dt if dt > 0 else float(polygloss_count)
        else:
            velocity = polygloss_count / max(1, len(sentences))

        density = demands_count / max(1, len(sentences))

        # Referential Cohesion (A6)
        cohesion_scores = []
        for i in range(len(sentences) - 1):
            w1 = get_content_words(sentences[i])
            w2 = get_content_words(sentences[i + 1])
            if w1 or w2:
                # Jaccard overlap
                intersection = len(w1 & w2)
                union = len(w1 | w2)
                cohesion_scores.append(intersection / union if union > 0 else 0.0)
            else:
                cohesion_scores.append(0.0)
        referential_cohesion = (
            sum(cohesion_scores) / len(cohesion_scores) if cohesion_scores else 0.0
        )

        # RST metrics
        rst_depth = max(depth_scores) if depth_scores else 1.0
        nucleus_ratio = nucleus_count / max(1, len(sentences))
        elaboration_density = elaboration_count / max(1, len(sentences))

        # Silence density & evasion flag
        silence_density = silence_markers_count / max(1, len(sentences))
        evasion_flag = silence_density > 0.05

        # Pressure index heuristic: silence + lack of nucleus structure (hedged complexity)
        pressure_index = (silence_density * 4.0) + ((1.0 - nucleus_ratio) * 2.0)

        # Intervention Timing CV (B9)
        if speaker_timestamps and len(speaker_timestamps) >= 3:
            sorted_times = sorted(speaker_timestamps)
            diffs = [
                sorted_times[i] - sorted_times[i - 1]
                for i in range(1, len(sorted_times))
            ]
            mean_diff = sum(diffs) / len(diffs)
            if mean_diff > 0:
                variance = sum((d - mean_diff) ** 2 for d in diffs) / len(diffs)
                intervention_timing_cv = math.sqrt(variance) / mean_diff
            else:
                intervention_timing_cv = 0.0
        else:
            intervention_timing_cv = 0.0

        logger.debug(
            "engagement.scored",
            speaker_id=speaker_id,
            score=base_score,
            velocity=velocity,
            density=density,
            referential_cohesion=referential_cohesion,
            rst_depth=rst_depth,
            nucleus_ratio=nucleus_ratio,
            silence_density=silence_density,
            evasion_flag=evasion_flag,
            pressure_index=pressure_index,
            intervention_timing_cv=intervention_timing_cv,
        )

        return DetailedEngagementScore(
            value=base_score,
            velocity=round(velocity, 4),
            density=round(density, 4),
            referential_cohesion=round(referential_cohesion, 4),
            rst_depth=round(rst_depth, 4),
            nucleus_ratio=round(nucleus_ratio, 4),
            elaboration_density=round(elaboration_density, 4),
            silence_density=round(silence_density, 4),
            evasion_flag=evasion_flag,
            pressure_index=round(pressure_index, 4),
            intervention_timing_cv=round(intervention_timing_cv, 4),
        )
