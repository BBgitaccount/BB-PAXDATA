# src/bb_paxdata/infrastructure/ai/frame_detection/five_w_one_h_extractor.py
"""LLM-based 5W1H extraction following Hamborg (2023) and TASK-A04 speech act extension.

[Academic Reference: Hamborg, F. (2023). NLP Techniques for Automated Frame Analysis.
Universität Göttingen. 5W1H extraction stage.]
"""

import structlog
from pydantic import BaseModel, Field

from bb_paxdata.application.domain.models.frame_annotation import FiveWOneH
from bb_paxdata.application.domain.models.segment import Segment
from bb_paxdata.application.domain.models.speech_act import (
    SpeechActClassification,
    SpeechActType,
)
from bb_paxdata.infrastructure.ai.clients.llm_client_protocol import LLMClientProtocol
from bb_paxdata.infrastructure.ai.recovery import RecoveryEngine

logger = structlog.get_logger(__name__)


class FiveWOneHSchema(BaseModel):
    """Schema for AI 5W1H extraction output validation."""

    who: list[str] = Field(default_factory=list)
    what: list[str] = Field(default_factory=list)
    when: list[str] = Field(default_factory=list)
    where: list[str] = Field(default_factory=list)
    why: list[str] = Field(default_factory=list)
    how: list[str] = Field(default_factory=list)
    primary_speech_act: str | None = Field(default=None)
    secondary_speech_act: str | None = Field(default=None)
    speech_act_confidence: float = Field(default=1.0)
    force_modifier: str | None = Field(default=None)


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

    def _safe_parse_speech_act(self, raw: str | None) -> tuple[SpeechActType, float]:
        """Safely parses raw speech act string to SpeechActType, returning default if invalid."""
        if not raw:
            return SpeechActType.ASSERTIVE, 0.5
        cleaned = raw.strip().upper()
        try:
            return SpeechActType(cleaned), 1.0
        except ValueError:
            valid_members = {m.value for m in SpeechActType}
            if cleaned in valid_members:
                return SpeechActType(cleaned), 1.0
            # Recovery: default to ASSERTIVE with penalized confidence
            return SpeechActType.ASSERTIVE, 0.5

    async def extract(self, segment: Segment) -> FiveWOneH:
        """Segment'teki 5W1H bilgilerini ve konuşma edimini çıkar.

        Prompt Registry: 5w1h_extraction@6.1.0
        Academic Ref: Hamborg (2023) — 5W1H Extraction
        """
        prompt = self._build_prompt(segment)

        try:
            raw_response = await self._llm.generate(
                prompt=prompt,
                temperature=0.0,
            )

            # Recovery Engine: 6-seviyeli JSON kurtarma
            recovery_result = self._recovery.recover(
                raw_response,
                raise_on_failure=False,
            )

            if not recovery_result.success or recovery_result.data is None:
                self._log.warning("5w1h_recovery_failed", segment_id=segment.id)
                return FiveWOneH()

            try:
                parsed = FiveWOneHSchema.model_validate(recovery_result.data)
            except Exception as e:
                self._log.warning(
                    "5w1h_validation_failed", segment_id=segment.id, error=str(e)
                )
                return FiveWOneH()

            # Parse primary and secondary speech acts
            primary, primary_conf = self._safe_parse_speech_act(
                parsed.primary_speech_act
            )
            secondary = None
            if parsed.secondary_speech_act:
                secondary, _ = self._safe_parse_speech_act(parsed.secondary_speech_act)

            speech_act = SpeechActClassification(
                primary_type=primary,
                secondary_type=secondary,
                confidence=min(parsed.speech_act_confidence, primary_conf),
                force_modifier=parsed.force_modifier,
            )

            return FiveWOneH(
                who=parsed.who,
                what=parsed.what,
                when=parsed.when,
                where=parsed.where,
                why=parsed.why,
                how=parsed.how,
                speech_act=speech_act,
            )
        except Exception as e:
            self._log.error(
                "5w1h_extraction_error", segment_id=segment.id, error=str(e)
            )
            return FiveWOneH()

    def _build_prompt(self, segment: Segment) -> str:
        """5W1H extraction prompt'u oluştur."""
        return f"""Extract the 5W1H information and classify the speech acts from the following diplomatic text segment.
Answer the questions: Who, What, When, Where, Why, and How based on the text.
Also classify the speech act of the main action. Choose primary and secondary speech acts from: ASSERTIVE, DIRECTIVE, COMMISSIVE, EXPRESSIVE, DECLARATIVE, INTERROGATIVE.
Identify any force modifier (e.g., "strongly", "categorically", "respectfully", "saygıyla", "şiddetle", "kesinlikle") used in the main action.

Text:
{segment.text}

Return a JSON object with the following structure:
{{
  "who": ["list of actors/entities involved"],
  "what": ["the main event or action described"],
  "when": ["temporal information or timestamps"],
  "where": ["geographical or contextual locations"],
  "why": ["reasons or motivations cited"],
  "how": ["mechanisms, methods, or conditions described"],
  "primary_speech_act": "ASSERTIVE|DIRECTIVE|COMMISSIVE|EXPRESSIVE|DECLARATIVE|INTERROGATIVE",
  "secondary_speech_act": "ASSERTIVE|DIRECTIVE|COMMISSIVE|EXPRESSIVE|DECLARATIVE|INTERROGATIVE or null",
  "speech_act_confidence": 0.95,
  "force_modifier": "strongly|categorically|respectfully|null"
}}
If a 5W1H field is not found in the text, return an empty array for that field.
"""
