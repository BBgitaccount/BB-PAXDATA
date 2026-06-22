from __future__ import annotations

import asyncio
from collections.abc import Coroutine, Sequence
from typing import TYPE_CHECKING, Any

import numpy as np
import structlog
from sklearn.feature_extraction.text import CountVectorizer

from bb_paxdata.application.domain.models.sbi_models import (
    SBIResult,
    SpeakerPosition,
)
from bb_paxdata.application.domain.services.sbi_protocols import (
    EngagementScorerProtocol,
    LIWCProtocol,
    StanceDensityProtocol,
    WordfishProtocol,
    WordscoresProtocol,
)

if TYPE_CHECKING:
    from bb_paxdata.application.domain.models.analysis import Analysis
    from bb_paxdata.application.domain.ports.i_gat_embedding_repository import (
        IGATEmbeddingRepository,
    )

logger = structlog.get_logger(__name__)


class SBICalculator:
    """
    Orchestrates the computation of Speaker-Based Index (SBI).

    Integrates multiple NLP services to produce a composite latent position
    and engagement profile for each speaker.

    (M-05) IGATEmbeddingRepository injected via constructor — domain service
    does NOT query DB directly. Clean Architecture DIP preserved.
    """

    def __init__(
        self,
        wordfish: WordfishProtocol,
        stance: StanceDensityProtocol,
        engagement: EngagementScorerProtocol,
        wordscores: WordscoresProtocol | None = None,
        liwc: LIWCProtocol | None = None,
        weights: tuple[float, float, float] = (0.6, 0.25, 0.15),
        gat_repo: IGATEmbeddingRepository | None = None,
    ):
        self.wordfish = wordfish
        self.stance = stance
        self.engagement = engagement
        self.wordscores = wordscores
        self.liwc = liwc
        self.weights = weights
        self._gat_repo = gat_repo

    async def compute(
        self, analyses: Sequence[Analysis], session_id: str = "session_default"
    ) -> SBIResult:
        """
        Orchestrate parallel computation of SBI components.

        Args:
            analyses: Sequence of Analysis objects representing speaker contributions.
            session_id: Session identifier for the speaker positions.

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

        if not isinstance(wordfish_thetas, dict):
            logger.error(
                "sbi_calculator.invalid_wordfish_type",
                type=type(wordfish_thetas).__name__,
            )
            wordfish_thetas = {sid: 0.0 for sid in speaker_ids}

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

            # Calculate LIWC scores if available
            liwc_clout = None
            liwc_analytic = None
            liwc_authenticity = None
            liwc_tone = None

            if self.liwc:
                speaker_text = " ".join(speaker_texts[sid])
                liwc_result = self.liwc.analyze(speaker_text)
                liwc_clout = liwc_result.clout
                liwc_analytic = liwc_result.analytic
                liwc_authenticity = liwc_result.authenticity
                liwc_tone = liwc_result.tone

            # Composite SBI
            sbi = alpha * theta + beta * stance + gamma * engagement

            pos = SpeakerPosition(
                speaker_id=sid,
                session_id=session_id,
                wordfish_theta=theta,
                stance_density=stance,
                engagement_score=engagement,
                liwc_clout=liwc_clout,
                liwc_analytic=liwc_analytic,
                liwc_authenticity=liwc_authenticity,
                liwc_tone=liwc_tone,
                sbi=sbi,
                alpha=alpha,
                beta=beta,
                gamma=gamma,
            )
            positions.append(pos)

        return SBIResult(positions=positions, pipeline_version="sbi@v1.0")
