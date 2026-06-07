import pytest
from bb_paxdata.application.domain.models.speech_act import SpeechActType
from bb_paxdata.application.domain.services.speech_act_classifier import (
    SpeechActClassifierService,
)


@pytest.mark.asyncio
async def test_heuristic_classification_defaults():
    service = SpeechActClassifierService()
    # Simple statement should default to ASSERTIVE
    res = await service.classify("Today is a sunny day in Ankara.")
    assert res.primary_type == SpeechActType.ASSERTIVE
    assert res.secondary_type is None
    assert res.force_modifier is None
    # Base confidence of 0.5 calibrated
    assert res.confidence > 0.0


@pytest.mark.asyncio
async def test_heuristic_classification_directive_and_modifier():
    service = SpeechActClassifierService()
    # "must" should trigger DIRECTIVE, "strongly" is a strong modifier
    res = await service.classify("You must accept our proposal strongly.")
    assert res.primary_type == SpeechActType.DIRECTIVE
    assert res.force_modifier == "strongly"
    assert res.is_coercive is True


@pytest.mark.asyncio
async def test_srl_context_boosting():
    service = SpeechActClassifierService()
    # Non-directive text upgraded to directive via SRL context obligation
    srl_context = {"args": [{"role": "ARGM-MOD", "text": "must"}]}
    res = await service.classify("We agree to the terms.", srl_context=srl_context)
    assert res.primary_type == SpeechActType.DIRECTIVE
    assert (
        res.secondary_type == SpeechActType.COMMISSIVE
    )  # "agree" was COMMISSIVE, became secondary
