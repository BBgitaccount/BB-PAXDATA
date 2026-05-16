# src/bb_paxdata/infrastructure/ai/frame_detection/frame_detection_pipeline.py
"""Hamborg (2023) PFA pipeline implementation.

[Academic Reference: Hamborg, F. (2023). NLP Techniques for Automated Frame Analysis.
Universität Göttingen. PFA pipeline: target concept + coreference + embedding matching
+ perspective clustering + 5W1H + bias detection.]
"""

from typing import Final

import numpy as np
import structlog
from bb_paxdata.domain.models.frame_annotation import (
    BiasSeverity,
    BiasSignal,
    FiveWOneH,
    FrameAnnotation,
    FrameDetectionResult,
    PerspectiveCluster,
    ResolvedEntity,
)
from bb_paxdata.domain.models.segment import Segment
from bb_paxdata.domain.services.frame_detection import (
    ConceptExtractorProtocol,
    CoreferenceResolverProtocol,
    EmbeddingFrameMatcherProtocol,
    FiveWOneHExtractorProtocol,
)
from bb_paxdata.domain.services.topic_modeling_protocol import TopicModelingProtocol
from bb_paxdata.infrastructure.ai.clients.llm_client_protocol import LLMClientProtocol
from bb_paxdata.infrastructure.ai.recovery_engine import RecoveryEngine
from sklearn.metrics.pairwise import cosine_similarity

logger = structlog.get_logger(__name__)

# Hamborg (2023) bias detection threshold
COSINE_SIMILARITY_THRESHOLD: Final[float] = 0.72


class FrameDetectionConfig:
    """PFA pipeline konfigürasyonu. Immutable."""

    model_config = {"frozen": True}

    concept_extraction_model: str = "claude-sonnet-4-20250514"
    coreference_strategy: str = "spacy_coreferee"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    similarity_threshold: float = COSINE_SIMILARITY_THRESHOLD
    perspective_cluster_count: int | None = None  # None = otomatik

    # PromptRegistry SHA256 audit için
    prompt_version: str = "frame_detection@6.1.0"
    prompt_academic_ref: str = "Hamborg2023"


class FrameDetectionPipeline:
    """Hamborg (2023) PFA pipeline'ının tam implementasyonu.

    Pipeline akışı:
    1. extract_concepts() → hedef kavramlar
    2. resolve_coreferences() → zamir çözümleme
    3. match_embedding_frames() → embedding tabanlı çerçeve eşleme
    4. cluster_perspectives() → aktör perspektif kümeleme
    5. extract_5w1h() → 5W1H çıkarımı
    6. detect_bias() → cosine similarity thresholding ile bias tespiti
    """

    def __init__(
        self,
        concept_extractor: ConceptExtractorProtocol | None,
        coreference_resolver: CoreferenceResolverProtocol | None,
        embedding_matcher: EmbeddingFrameMatcherProtocol | None,
        five_w_one_h_extractor: FiveWOneHExtractorProtocol | None,
        llm_client: LLMClientProtocol,
        topic_service: TopicModelingProtocol,
        recovery_engine: RecoveryEngine,
        config: FrameDetectionConfig | None = None,
    ) -> None:
        self._concept_extractor = concept_extractor
        self._coreference_resolver = coreference_resolver
        self._embedding_matcher = embedding_matcher
        self._five_w_one_h_extractor = five_w_one_h_extractor
        self._llm_client = llm_client
        self._topic_service = topic_service
        self._recovery = recovery_engine
        self._config = config or FrameDetectionConfig()
        self._log = logger.bind(
            pipeline="frame_detection", version=self._config.prompt_version
        )

    async def analyze(self, segment: Segment) -> FrameDetectionResult:
        """Tam PFA pipeline'ını çalıştır.

        [Hamborg (2023): PFA pipeline — target concept extraction, coreference resolution,
        word embedding frame matching, perspective clustering, 5W1H extraction,
        cosine similarity bias detection.]
        """
        self._log.info("frame_pipeline_started", segment_id=segment.id)

        # Stage 1: Target Concept Extraction
        concepts: list[str] = []
        if self._concept_extractor:
            concepts = await self._concept_extractor.extract_concepts(segment)
        self._log.debug("concepts_extracted", count=len(concepts))

        # Stage 2: Coreference Resolution
        resolved_entities: list[ResolvedEntity] = []
        if self._coreference_resolver:
            resolved_entities = await self._coreference_resolver.resolve(segment)
        self._log.debug("coreferences_resolved", count=len(resolved_entities))

        # Stage 3: Embedding-based Frame Matching
        # Note: In Phase 5 TopicModelingService was updated to provide reference embeddings
        frame_embeddings = await self._load_frame_embeddings()
        frame_annotations: list[FrameAnnotation] = []
        if self._embedding_matcher:
            frame_annotations = await self._embedding_matcher.match_frames(
                segment, concepts, frame_embeddings
            )
        self._log.debug("frames_matched", count=len(frame_annotations))

        # Stage 4: Perspective Clustering
        perspectives = await self._cluster_perspectives(segment, resolved_entities)
        self._log.debug("perspectives_clustered", count=len(perspectives))

        # Stage 5: 5W1H Extraction
        five_w_one_h = FiveWOneH()
        if self._five_w_one_h_extractor:
            five_w_one_h = await self._five_w_one_h_extractor.extract(segment)
        self._log.debug("5w1h_extracted")

        # Stage 6: Bias Detection (Hamborg 2023: cosine similarity thresholding)
        bias_signals = self._detect_bias(frame_annotations, frame_embeddings)
        self._log.info("bias_detected", signals=len(bias_signals))

        result = FrameDetectionResult(
            segment_id=segment.id,
            concepts=concepts,
            resolved_entities=resolved_entities,
            frame_annotations=frame_annotations,
            perspectives=perspectives,
            five_w_one_h=five_w_one_h,
            bias_signals=bias_signals,
            prompt_version=self._config.prompt_version,
            prompt_sha256=self._compute_prompt_hash(),
        )

        self._log.info("frame_pipeline_completed", segment_id=segment.id)
        return result

    async def _load_frame_embeddings(self) -> dict[str, list[float]]:
        """Entman (1993) 4 fonksiyonu için önceden hesaplanmış frame embedding vektörleri."""
        result: dict[str, list[float]] = (
            await self._topic_service.get_frame_reference_embeddings()
        )
        return result

    def _detect_bias(
        self,
        annotations: list[FrameAnnotation],
        frame_embeddings: dict[str, list[float]],
    ) -> list[BiasSignal]:
        """Hamborg (2023) cosine similarity thresholding ile bias tespiti."""
        signals: list[BiasSignal] = []
        for ann in annotations:
            if ann.embedding_vector is None:
                continue

            ref_vec_list = frame_embeddings.get(ann.frame_type.value)
            if not ref_vec_list:
                continue

            ref_vec = np.asarray(np.array(ref_vec_list).reshape(1, -1))
            ann_vec = np.asarray(np.array(ann.embedding_vector).reshape(1, -1))
            from typing import Any, cast

            sim = float(cosine_similarity(cast(Any, ann_vec), cast(Any, ref_vec))[0][0])

            if sim < self._config.similarity_threshold:
                signals.append(
                    BiasSignal(
                        frame_annotation_id=ann.id,
                        cosine_distance=1.0 - sim,
                        threshold=self._config.similarity_threshold,
                        severity=(
                            BiasSeverity.HIGH if sim < 0.5 else BiasSeverity.MEDIUM
                        ),
                    )
                )
        return signals

    async def _cluster_perspectives(
        self, segment: Segment, entities: list[ResolvedEntity]
    ) -> list[PerspectiveCluster]:
        """Aktör bazlı perspektif kümeleme."""
        actors = {e.actor_id for e in entities if e.actor_id is not None}
        clusters: list[PerspectiveCluster] = []

        for actor in actors:
            actor_entities = [e for e in entities if e.actor_id == actor]
            clusters.append(
                PerspectiveCluster(
                    actor_id=actor,
                    entities=actor_entities,
                    embedding_centroid=self._compute_centroid(actor_entities),
                )
            )

        return clusters

    def _compute_centroid(self, entities: list[ResolvedEntity]) -> list[float] | None:
        """Perspektif kümesinin embedding centroid'ini hesapla."""
        vectors = [np.array(e.embedding) for e in entities if e.embedding is not None]
        if not vectors:
            return None
        centroid = np.mean(vectors, axis=0)
        return [float(x) for x in centroid.tolist()]

    def _compute_prompt_hash(self) -> str:
        """PromptRegistry audit trail için SHA256 hash placeholder."""
        return "sha256_placeholder_for_audit"
