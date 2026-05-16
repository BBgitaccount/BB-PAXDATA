from __future__ import annotations

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


class EngagementAnalyzer:
    """
    Implements Martin & White (2005) Appraisal Theory Engagement analysis.

    Academic Source:
    Martin, J. R., & White, P. R. (2005). The language of evaluation:
    Appraisal in English. Palgrave Macmillan.
    """

    def __init__(self) -> None:
        self.markers = ENGAGEMENT_MARKERS
        self.graduation = GRADUATION_FORCE

    async def score(self, sentences: list[str], speaker_id: str) -> float:
        """
        Return engagement score ∈ [0, 1].
        Formula: (polygloss_count / total_engagement_markers) × avg(graduation_force)
        """
        if not sentences:
            return 0.0

        polygloss_count = 0
        total_markers = 0
        force_scores = []

        for sent in sentences:
            sent_lower = sent.lower()
            is_polygloss = False

            # Check for polygloss markers
            for category, markers in self.markers.items():
                for marker in markers:
                    if marker in sent_lower:
                        is_polygloss = True
                        total_markers += 1

            if is_polygloss:
                polygloss_count += 1

            # Check for graduation force
            for booster in self.graduation["boosters"]:
                if booster in sent_lower:
                    force_scores.append(1.0)
            for hedge in self.graduation["hedges"]:
                if hedge in sent_lower:
                    force_scores.append(0.5)

        if total_markers == 0:
            # If no engagement markers found, it's mostly monogloss
            return 0.0

        avg_force = (
            sum(force_scores) / len(force_scores) if force_scores else 0.75
        )  # Default force

        engagement_score = (polygloss_count / total_markers) * avg_force
        # Clip to [0, 1]
        engagement_score = min(max(engagement_score, 0.0), 1.0)

        logger.debug(
            "engagement.scored",
            speaker_id=speaker_id,
            score=engagement_score,
            polygloss_ratio=polygloss_count / len(sentences),
        )

        return engagement_score
