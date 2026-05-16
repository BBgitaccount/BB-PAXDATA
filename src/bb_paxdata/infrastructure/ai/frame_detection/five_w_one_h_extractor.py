# src/bb_paxdata/infrastructure/ai/frame_detection/five_w_one_h_extractor.py
"""LLM-based 5W1H extraction following Hamborg (2023).

[Academic Reference: Hamborg, F. (2023). NLP Techniques for Automated Frame Analysis.
Universität Göttingen. 5W1H extraction stage.]
"""

import structlog
from bb_paxdata.domain.models.frame_annotation import FiveWOneH
from bb_paxdata.domain.models.segment import Segment
from bb_paxdata.infrastructure.ai.clients.llm_client_protocol import LLMClientProtocol
from bb_paxdata.infrastructure.ai.recovery_engine import RecoveryEngine
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


class FiveWOneHSchema(BaseModel):
    """Schema for AI 5W1H extraction output validation."""

    who: list[str] = Field(default_factory=list)
    what: list[str] = Field(default_factory=list)
    when: list[str] = Field(default_factory=list)
    where: list[str] = Field(default_factory=list)
    why: list[str] = Field(default_factory=list)
    how: list[str] = Field(default_factory=list)


class LLMFiveWOneHExtractor:
    """LLM tabanlı 5W1H çıkarımı.

    Hamborg (2023): '5W1H çıkarımı' — metindeki temel gazetecilik sorularının
    cevaplarının tespiti: Who, What, When, Where, Why, How.
    """

    def __init__(self, llm_client: LLMClientProtocol, recovery: RecoveryEngine) -> None:
        self._llm = llm_client
        self._recovery = recovery
        self._prompt_version = "5w1h_extraction@6.1.0"
        self._log = logger.bind(service="5w1h_extractor", version=self._prompt_version)

    async def extract(self, segment: Segment) -> FiveWOneH:
        """Segment'teki 5W1H bilgilerini çıkar.

        Prompt Registry: 5w1h_extraction@6.1.0
        Academic Ref: Hamborg (2023) — 5W1H Extraction
        """
        prompt = self._build_prompt(segment)

        try:
            raw_response = await self._llm.generate(
                prompt=prompt,
                temperature=0.0,
                # json_schema=FiveWOneHSchema
            )

            # Recovery Engine: 6-seviyeli JSON kurtarma
            parsed = await self._recovery.recover(raw_response, FiveWOneHSchema)

            if parsed is None or not isinstance(parsed, FiveWOneHSchema):
                self._log.warning("5w1h_recovery_failed", segment_id=segment.id)
                return FiveWOneH()

            return FiveWOneH(
                who=parsed.who,
                what=parsed.what,
                when=parsed.when,
                where=parsed.where,
                why=parsed.why,
                how=parsed.how,
            )
        except Exception as e:
            self._log.error(
                "5w1h_extraction_error", segment_id=segment.id, error=str(e)
            )
            return FiveWOneH()

    def _build_prompt(self, segment: Segment) -> str:
        """5W1H extraction prompt'u oluştur."""
        return f"""Extract the 5W1H information from the following diplomatic text segment.
Answer the questions: Who, What, When, Where, Why, and How based on the text.

Text:
{segment.text}

Return a JSON object with the following structure:
{{
  "who": ["list of actors/entities involved"],
  "what": ["the main event or action described"],
  "when": ["temporal information or timestamps"],
  "where": ["geographical or contextual locations"],
  "why": ["reasons or motivations cited"],
  "how": ["mechanisms, methods, or conditions described"]
}}
If a field is not found in the text, return an empty array for that field.
"""
