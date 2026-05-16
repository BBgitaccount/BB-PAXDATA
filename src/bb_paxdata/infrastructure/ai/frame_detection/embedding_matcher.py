# src/bb_paxdata/infrastructure/ai/frame_detection/embedding_matcher.py
"""SBERT embedding + cosine similarity based frame matching.

[Academic Reference: Hamborg, F. (2023). NLP Techniques for Automated Frame Analysis.
Universität Göttingen. Word embedding frame matching.]
"""

import numpy as np
import structlog
from bb_paxdata.domain.enums.frame_type import FrameType
from bb_paxdata.domain.models.frame_annotation import FrameAnnotation
from bb_paxdata.domain.models.segment import Segment
from bb_paxdata.domain.services.topic_modeling_protocol import TopicModelingProtocol
from sklearn.metrics.pairwise import cosine_similarity

logger = structlog.get_logger(__name__)

# Hamborg (2023) bias detection / matching threshold
COSINE_SIMILARITY_THRESHOLD = 0.72


class SBERTFrameMatcher:
    """SBERT embedding + cosine similarity tabanlı çerçeve eşleme.

    Hamborg (2023): 'Word embedding üzerinden çerçeve kategorisi eşleme'.
    Entman (1993) 4 fonksiyonu (problem, cause, moral, remedy) için referans
    embedding vektörleri ile segment embedding'lerinin karşılaştırılması.
    """

    def __init__(self, topic_service: TopicModelingProtocol) -> None:
        self._topic_service = topic_service
        self._log = logger.bind(service="sbert_frame_matcher")
        self._threshold = COSINE_SIMILARITY_THRESHOLD

    async def match_frames(
        self,
        segment: Segment,
        concepts: list[str],
        frame_embeddings: dict[str, list[float]],
    ) -> list[FrameAnnotation]:
        """Segment embedding'lerini referans frame embedding'leriyle eşleştir.

        Formül: similarity = cosine_similarity(segment_vec, frame_vec)
        Eşik: 0.72 (Hamborg 2023)
        """
        try:
            # Segment embedding'ini Faz 5 TopicModelingService'den al
            # Note: We assume the service provides a method to embed a single segment
            segment_vec = await self._topic_service.embed_segments([segment])
            if not segment_vec or segment.id not in segment_vec:
                self._log.warning("segment_embedding_missing", segment_id=segment.id)
                return []

            vec = segment_vec[segment.id]
            seg_np = np.array(vec).reshape(1, -1)
            annotations: list[FrameAnnotation] = []

            for frame_type_str, ref_vec in frame_embeddings.items():
                if not ref_vec:
                    continue

                ref_np = np.array(ref_vec).reshape(1, -1)
                sim = float(cosine_similarity(seg_np, ref_np)[0][0])

                if sim >= self._threshold:
                    try:
                        # Attempt to map to Enum
                        frame_type = FrameType(frame_type_str)
                    except ValueError:
                        # Handle cases where frame_type_str might be legacy or slightly different
                        self._log.debug(
                            "unknown_frame_type_string", frame_type=frame_type_str
                        )
                        continue

                    annotations.append(
                        FrameAnnotation(
                            id=f"{segment.id}_{frame_type.value}",
                            frame_type=frame_type,
                            confidence=sim,
                            embedding_vector=vec,
                            matched_concepts=[
                                c for c in concepts if c.lower() in segment.text.lower()
                            ],
                            keyword_weight=sim,  # Initial weight based on similarity
                            sentence_index=0,  # Default, can be refined if multiple sentences
                            cue_source="hamborg_embedding",
                        )
                    )

            self._log.debug(
                "frame_matches_completed", count=len(annotations), segment_id=segment.id
            )
            return annotations
        except Exception as e:
            self._log.error("frame_matching_error", segment_id=segment.id, error=str(e))
            return []
