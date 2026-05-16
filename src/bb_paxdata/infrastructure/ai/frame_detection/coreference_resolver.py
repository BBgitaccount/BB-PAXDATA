# src/bb_paxdata/infrastructure/ai/frame_detection/coreference_resolver.py
"""spaCy + coreferee based coreference resolution.

[Academic Reference: Hamborg, F. (2023). NLP Techniques for Automated Frame Analysis.
Universität Göttingen. Coreference Resolution stage.]
"""

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spacy.language import Language

import spacy
import structlog
from bb_paxdata.domain.models.frame_annotation import ResolvedEntity
from bb_paxdata.domain.models.segment import Segment

logger = structlog.get_logger(__name__)


class SpacyCoreferenceResolver:
    """spaCy + coreferee tabanlı coreference çözümleme.

    Hamborg (2023): Coreference resolution — zamirlerin (he, she, it, they) ve
    possessive'lerin metindeki gerçek referanslarına bağlanması. Diplomatik metinde
    "they" bir ülkeyi, "it" bir anlaşmayı referans edebilir.
    """

    def __init__(self, nlp: Language) -> None:
        self._nlp = nlp
        self._log = logger.bind(service="coreference_resolver")

    async def resolve(self, segment: Segment) -> list[ResolvedEntity]:
        """Zamirleri ve referansları çözümle.

        Not: spaCy coreferee senkron çalışır, ancak async context'te
        asyncio.to_thread() kullanılmalıdır.
        """
        try:
            doc = await asyncio.to_thread(self._nlp, segment.text)

            if not hasattr(doc._, "coref_chains") or doc._.coref_chains is None:
                self._log.warning("coreferee_not_available_or_no_chains")
                return []

            entities: list[ResolvedEntity] = []
            seen_spans: set[tuple[int, int]] = set()

            for chain in doc._.coref_chains:
                # Her zincirin en erkek mention'ını (genellikle ilki) ana referans olarak al
                # chain[0] is a list of token indices
                main_mention_indices = chain[0]
                main_span = doc[main_mention_indices[0] : main_mention_indices[-1] + 1]

                for mention in chain:
                    start, end = mention[0], mention[-1] + 1
                    if (start, end) in seen_spans:
                        continue
                    seen_spans.add((start, end))

                    span = doc[start:end]
                    entities.append(
                        ResolvedEntity(
                            text=span.text,
                            start_idx=span.start_char,
                            end_idx=span.end_char,
                            label=(
                                span.root.ent_type_
                                if span.root.ent_type_
                                else "UNKNOWN"
                            ),
                            main_reference=main_span.text,
                            actor_id=self._infer_actor(span),
                            embedding=None,  # Will be populated later if needed
                        )
                    )

            return entities
        except Exception as e:
            self._log.error(
                "coreference_resolution_error", segment_id=segment.id, error=str(e)
            )
            return []

    def _infer_actor(self, span: spacy.tokens.Span) -> str | None:
        """Span'dan aktör (ülke/kurum) çıkarımı yap.

        Diplomatik metinde GPE (Geopolitical Entity), ORG (Organization) ve
        NORP (Nationalities or religious or political groups) label'ları aktör adayıdır.
        """
        # Check span's root ent_type or any entity in span
        if span.root.ent_type_ in ("GPE", "ORG", "NORP"):
            return span.text

        # Fallback: check if the span itself is an entity
        for ent in span.ents:
            if ent.label_ in ("GPE", "ORG", "NORP"):
                return ent.text

        return None
