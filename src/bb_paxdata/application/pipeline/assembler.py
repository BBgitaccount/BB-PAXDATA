from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from bb_paxdata.application.pipeline.sbi_calculator import SBICalculator
from bb_paxdata.domain.enums.signal_type import SignalType
from bb_paxdata.domain.models.ai_analysis import AIAnalysisResult
from bb_paxdata.domain.models.analysis import Analysis
from bb_paxdata.domain.models.bilateral_sentiment import BilateralSentiment
from bb_paxdata.domain.models.frame_annotation import (
    FrameDetectionResult,
    FrameSalienceResult,
)
from bb_paxdata.domain.models.negation_cue import NegationCue
from bb_paxdata.domain.models.power_index import PowerIndex
from bb_paxdata.domain.models.risk_signal import RiskSignal
from bb_paxdata.domain.models.sbi_models import SBIResult
from bb_paxdata.domain.models.segment import Segment
from bb_paxdata.domain.models.topic import TopicResult
from bb_paxdata.domain.models.topic_synthesis import TopicSynthesis
from bb_paxdata.infrastructure.nlp.lodp_service import LODPService

logger = logging.getLogger(__name__)


class AnalysisAssembler:
    """
    Alt-servis dict çıktılarını + AIAnalysisResult'ı
    doğrulanmış bir Analysis (Pydantic) nesnesine dönüştürür.

    LODP (Monroe 2009) kullanarak ayırt edici kelime çıkarımı yapar.
    """

    def __init__(
        self,
        lodp_service: LODPService | None = None,
        sbi_calculator: SBICalculator | None = None,
    ) -> None:
        self.lodp = lodp_service or LODPService()
        self.sbi_calculator = sbi_calculator

    def assemble(
        self,
        source_text: str,
        language: str,
        ner_result: dict[str, Any],
        tokenizer_result: dict[str, Any],
        ai_result: AIAnalysisResult,
        negation_cues: Sequence[NegationCue] = (),
        risk_signals: Sequence[RiskSignal] = (),
        power_indices: dict[str, PowerIndex] | None = None,
        topic_result: TopicResult | None = None,
        frame_detection: FrameDetectionResult | None = None,
        frame_salience: FrameSalienceResult | None = None,
        sbi_result: SBIResult | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Analysis:
        """
        Tüm alt-servis çıktılarını birleştirip doğrulanmış Analysis üretir.
        """
        metadata = metadata or {}

        analysis = Analysis(
            id=metadata.get("id", f"anal-{uuid.uuid4().hex[:8]}"),
            source_text=source_text,
            language=language,
            timestamp=metadata.get("timestamp", datetime.now(timezone.utc).isoformat()),
            # ── NLP Alanları ──
            entities=ner_result.get("entities", []),
            tokens=tokenizer_result.get("tokens", []),
            sentences=tokenizer_result.get("sentences", []),
            negation_cues=negation_cues,
            risk_signals=risk_signals,
            power_indices=power_indices or {},
            sentence_count=tokenizer_result.get("sentence_count", 0),
            # ── AI Alanları (AIAnalysisResult'tan güvenli aktarım) ──
            ai_sentiment_score=ai_result.sentiment_score,
            ai_risk_score=ai_result.risk_score,
            ai_sentiment_label=ai_result.sentiment_label,
            ai_risk_factors=ai_result.risk_factors,
            ai_summary=ai_result.summary,
            ai_key_claims=ai_result.key_claims,
            # ── Prompt Audit Trail ──
            prompt_version=ai_result.prompt_version,
            prompt_hash=ai_result.prompt_hash,
            model_name=ai_result.model_name,
            # ── Framing Alanları ──
            frame_detection=frame_detection,
            frame_salience=frame_salience,
            # ── SBI Alanları ──
            sbi_result=sbi_result,
        )

        # ── Faz 5: Topic Modeling Entegrasyonu ──
        if topic_result:
            # 1. TopicSynthesis oluştur
            # Şimdilik basitleştirilmiş bir yaklaşım: ilk segmentin skorlarını alıyoruz
            # (Çünkü CollectStage'de tek bir segment olarak işledik)
            if topic_result.assignments:
                primary_assign = topic_result.assignments[0]
                topic_synth = TopicSynthesis(
                    panel_id=metadata.get("panel_id", "default"),
                    country=metadata.get("speaker_country", "unknown"),
                    topic_scores=primary_assign.topic_scores,
                    topic_label=topic_result.topic_keywords.get(
                        primary_assign.primary_topic, {}
                    ).get(
                        "label", primary_assign.primary_topic
                    ),  # label alanı yoksa primary_topic
                    topic_keywords=topic_result.topic_keywords.get(
                        primary_assign.primary_topic, {}
                    ),
                )

                # DNA node mapping (Phase 4 DiscourseFlow varsa)
                node_mapping = {}
                updated_discourse_flow = analysis.discourse_flow
                if analysis.discourse_flow:
                    node_mapping = self._map_topics_to_nodes(
                        topic_result, analysis.discourse_flow.edges
                    )
                    # DiscourseFlow'a topic_id'leri ekle
                    updated_discourse_flow = analysis.discourse_flow.model_copy(
                        update={"topic_ids": list(topic_result.topic_keywords.keys())}
                    )

                # Immutable update
                analysis = analysis.model_copy(
                    update={
                        "topic_synthesis": topic_synth,
                        "topic_node_mapping": node_mapping,
                        "discourse_flow": updated_discourse_flow,
                    }
                )

        logger.debug(
            f"Assembly tamamlandı: id={analysis.id}, " f"language={analysis.language}"
        )
        return analysis

    def _map_topics_to_nodes(
        self,
        topic_result: TopicResult,
        edges: Sequence[Any],  # NetworkEdge
    ) -> dict[str, list[str]]:
        """BERTopic konularını DNA ağ düğümlerine eşler.

        Eşleme kuralı: Bir konunun top-3 kelimesinden biri, bir düğümün (konsept)
        ID'sinde (veya etiketinde) geçiyorsa eşleştir.
        """
        mapping: dict[str, list[str]] = {}
        for topic_id, keywords in topic_result.topic_keywords.items():
            top_words = set(list(keywords.keys())[:3])
            matched_nodes = []
            for edge in edges:
                # NetworkEdge modelinde concept_id olduğunu biliyoruz
                concept_id = getattr(edge, "concept_id", "").lower()
                # Concept ID'si genellikle kelime bazlıdır (ör: "BM_Reformu")
                node_words = set(concept_id.replace("_", " ").split())
                if top_words & node_words:
                    matched_nodes.append(concept_id)
            mapping[topic_id] = list(set(matched_nodes))
        return mapping

    async def enrich_with_lodp(
        self,
        segments: list[Segment],
        reference_segments: list[Segment] | None = None,
    ) -> list[Segment]:
        """
        Segmentleri LODP z-skoruyla zenginleştirir.

        Reference:
            - Monroe, B.L. et al. (2009). Fightin' Words.
        """
        if not reference_segments or len(segments) < 1:
            return segments

        enriched_segments = []
        for i, segment in enumerate(segments):
            # Karşılaştırma için referans segment seç (veya tüm referansları birleştir)
            ref = reference_segments[i % len(reference_segments)]
            lodp_results = await self.lodp.analyze_segment_pair(segment, ref)

            # key_phrases: LODP z_skor'u yüksek olan kelimeler (|z| > 1.96)
            key_phrases = [r.word for r in lodp_results if abs(r.z_score) > 1.96]

            # Segment'i immutable güncelleme
            enriched = segment.model_copy(
                update={"key_phrases": key_phrases, "lodp_results": lodp_results}
            )
            enriched_segments.append(enriched)

        return enriched_segments

    def _calculate_commitment_cost_ratio(self, signals: Sequence[RiskSignal]) -> float:
        """COSTLY_SIGNAL oranı = commitment cost proxy (Trager 2010)."""
        if not signals:
            return 0.0
        costly_count = sum(
            1 for s in signals if s.signal_type == SignalType.COSTLY_SIGNAL
        )
        return costly_count / len(signals)

    async def build_bilateral_sentiment(
        self,
        panel_id: str,
        speaker_a: str,
        speaker_b: str,
        sentiment_delta: float,
        power_a: PowerIndex,
        power_b: PowerIndex,
        risk_signals: Sequence[RiskSignal],
    ) -> BilateralSentiment:
        """Segment üzerinde ikili sentiment + güç asimetrisi hesapla (Trager/Zagare/Van Dijk)."""

        commitment_ratio = self._calculate_commitment_cost_ratio(risk_signals)

        # Risk severity: max escalation multiplier
        risk_severity = max(
            (s.escalation_multiplier for s in risk_signals), default=1.0
        )

        return BilateralSentiment(
            from_country=speaker_a,
            to_country=speaker_b,
            panel_id=panel_id,
            sentiment_delta=sentiment_delta,
            power_index_a=power_a,
            power_index_b=power_b,
            power_level_a=power_a.total_power_index,
            power_level_b=power_b.total_power_index,
            commitment_cost_ratio=commitment_ratio,
            risk_severity=risk_severity,
            demand_weight=1.0,  # Default
        )
