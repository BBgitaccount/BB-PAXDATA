from __future__ import annotations

import asyncio
from collections.abc import Coroutine, Sequence
from typing import TYPE_CHECKING, Any

import numpy as np
import structlog
from bb_paxdata.domain.models.sbi_models import (
    SBIResult,
    SpeakerPosition,
)
from bb_paxdata.domain.services.sbi_protocols import (
    EngagementScorerProtocol,
    StanceDensityProtocol,
    WordfishProtocol,
    WordscoresProtocol,
)
from sklearn.feature_extraction.text import CountVectorizer

if TYPE_CHECKING:
    from bb_paxdata.domain.models.analysis import Analysis

logger = structlog.get_logger(__name__)


class SBICalculator:
    """
    Orchestrates the computation of Speaker-Based Index (SBI).

    Integrates multiple NLP services to produce a composite latent position
    and engagement profile for each speaker.
    """

    def __init__(
        self,
        wordfish: WordfishProtocol,
        stance: StanceDensityProtocol,
        engagement: EngagementScorerProtocol,
        wordscores: WordscoresProtocol | None = None,
        weights: tuple[float, float, float] = (0.6, 0.25, 0.15),
    ):
        self.wordfish = wordfish
        self.stance = stance
        self.engagement = engagement
        self.wordscores = wordscores
        self.weights = weights

    async def compute(self, analyses: Sequence[Analysis]) -> SBIResult:
        """
        Orchestrate parallel computation of SBI components.

        Args:
            analyses: Sequence of Analysis objects representing speaker contributions.

        Returns:
            SBIResult containing SpeakerPosition for each unique speaker.
        """
        if not analyses:
            return SBIResult(positions=[])

        # 1. Aggregate text by speaker
        speaker_texts: dict[str, list[str]] = {}
        speaker_tokens: dict[str, list[str]] = {}
        speaker_sentences: dict[str, list[str]] = {}

        for analysis in analyses:
            sid = analysis.speaker_id or "unknown"
            speaker_texts.setdefault(sid, []).append(analysis.source_text)
            speaker_tokens.setdefault(sid, []).extend(analysis.tokens)
            speaker_sentences.setdefault(sid, []).extend(analysis.sentences)

        speaker_ids = sorted(speaker_texts.keys())
        aggregated_texts = [" ".join(speaker_texts[sid]) for sid in speaker_ids]

        # 2. Build Document-Term Matrix (DTM) for Wordfish
        vectorizer = CountVectorizer(stop_words="english", max_features=5000)
        dtm_result = vectorizer.fit_transform(aggregated_texts)
        dtm = (
            dtm_result.toarray()
            if hasattr(dtm_result, "toarray")
            else np.asarray(dtm_result)
        )

        # 3. Run computations in parallel
        # - Wordfish (Global)
        # - Stance & Engagement (Per speaker)

        tasks: list[asyncio.Task[Any] | Coroutine[Any, Any, Any]] = []
        # Wordfish task
        tasks.append(self.wordfish.fit_transform(dtm, speaker_ids))

        # Stance tasks
        for sid in speaker_ids:
            tasks.append(self.stance.calculate(speaker_tokens[sid], sid))

        # Engagement tasks
        for sid in speaker_ids:
            tasks.append(self.engagement.score(speaker_sentences[sid], sid))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Parse results
        wordfish_thetas = results[0]
        if isinstance(wordfish_thetas, BaseException):
            logger.error("sbi_calculator.wordfish_failed", error=str(wordfish_thetas))
            wordfish_thetas = {sid: 0.0 for sid in speaker_ids}

        assert isinstance(wordfish_thetas, dict)

        stance_scores = results[1 : 1 + len(speaker_ids)]
        engagement_scores = results[1 + len(speaker_ids) :]

        # 4. Construct SpeakerPosition objects
        positions = []
        alpha, beta, gamma = self.weights

        for i, sid in enumerate(speaker_ids):
            theta = float(wordfish_thetas.get(sid, 0.0))
            stance_val = stance_scores[i]
            stance = (
                float(stance_val) if not isinstance(stance_val, BaseException) else 0.0
            )
            engagement_val = engagement_scores[i]
            engagement = (
                float(engagement_val)
                if not isinstance(engagement_val, BaseException)
                else 0.0
            )

            # Composite SBI
            sbi = alpha * theta + beta * stance + gamma * engagement

            pos = SpeakerPosition(
                speaker_id=sid,
                session_id="session_default",  # Can be extracted from metadata if available
                wordfish_theta=theta,
                stance_density=stance,
                engagement_score=engagement,
                sbi=sbi,
                alpha=alpha,
                beta=beta,
                gamma=gamma,
            )
            positions.append(pos)

        return SBIResult(positions=positions, pipeline_version="sbi@v1.0")
