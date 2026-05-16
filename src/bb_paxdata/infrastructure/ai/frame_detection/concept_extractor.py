# src/bb_paxdata/infrastructure/ai/frame_detection/concept_extractor.py
"""LLM-based target concept extraction following Hamborg (2023).

[Academic Reference: Hamborg, F. (2023). NLP Techniques for Automated Frame Analysis.
Universität Göttingen. Target Concept Extraction stage.]
"""

import structlog
from bb_paxdata.domain.models.segment import Segment
from bb_paxdata.infrastructure.ai.clients.llm_client_protocol import LLMClientProtocol
from bb_paxdata.infrastructure.ai.recovery_engine import RecoveryEngine
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


class ConceptExtractionSchema(BaseModel):
    """Schema for AI concept extraction output validation."""

    concepts: list[str] = Field(description="List of extracted target concepts")


class LLMConceptExtractor:
    """LLM tabanlı hedef kavram çıkarımı.

    Hamborg (2023): 'Hedef kavram çıkarımı' — metindeki ana konu ve kavramların
    tespiti. Diplomatik metinlerde bu genellikle anlaşmazlık konusu olan varlıklardır.
    """

    def __init__(self, llm_client: LLMClientProtocol, recovery: RecoveryEngine) -> None:
        self._llm = llm_client
        self._recovery = recovery
        self._prompt_version = "concept_extraction@6.1.0"
        self._log = logger.bind(
            service="concept_extractor", version=self._prompt_version
        )

    async def extract_concepts(self, segment: Segment) -> list[str]:
        """Segment'teki hedef kavramları çıkar.

        Prompt Registry: concept_extraction@6.1.0
        Academic Ref: Hamborg (2023) — Target Concept Extraction
        """
        prompt = self._build_prompt(segment)

        try:
            raw_response = await self._llm.generate(
                prompt=prompt,
                temperature=0.0,  # Deterministik
                # JSON schema support depends on client implementation
            )

            # Recovery Engine: 6-seviyeli JSON kurtarma
            parsed = await self._recovery.recover(raw_response, ConceptExtractionSchema)

            if parsed is None or not isinstance(parsed, ConceptExtractionSchema):
                self._log.warning(
                    "concept_extraction_recovery_failed", segment_id=segment.id
                )
                return []

            return parsed.concepts
        except Exception as e:
            self._log.error(
                "concept_extraction_error", segment_id=segment.id, error=str(e)
            )
            return []

    def _build_prompt(self, segment: Segment) -> str:
        """Concept extraction prompt'u oluştur.

        SHA256 Audit: Bu prompt'un versiyonu ve hash'i PromptRegistry'de saklanır.
        """
        # Note: In a real implementation, this would be fetched from PromptRegistry
        return f"""Extract the key target concepts from the following diplomatic text segment.
These are the main subjects of dispute, negotiation, or discussion.

Text:
{segment.text}

Return a JSON object with a "concepts" array containing strings.
Each concept should be a noun phrase representing a key issue.
Example: {{"concepts": ["border security", "bilateral trade", "human rights"]}}
"""
