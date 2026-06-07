"""
Unit tests for presupposition domain models.
"""

import pytest
from bb_paxdata.application.domain.models.presupposition import (
    Presupposition,
    PresuppositionExtractionResult,
    TriggerType,
    VerificationMethod,
)


def test_presupposition_creation():
    """Test basic Presupposition model creation."""
    presup = Presupposition(
        trigger_word="know",
        trigger_type=TriggerType.FACTIVE_VERB,
        presupposed_content="Turkey knows the proposal",
        confidence=0.85,
        segment_id="seg_001",
        speaker="Turkey",
    )

    assert presup.trigger_word == "know"
    assert presup.trigger_type == TriggerType.FACTIVE_VERB
    assert presup.confidence == 0.85
    assert presup.segment_id == "seg_001"
    assert presup.speaker == "Turkey"
    assert presup.verification_method is None


def test_presupposition_confidence_validation():
    """Test confidence score validation."""
    # Valid confidence
    Presupposition(
        trigger_word="know",
        trigger_type=TriggerType.FACTIVE_VERB,
        presupposed_content="test",
        confidence=0.5,
        segment_id="seg_001",
        speaker="Turkey",
    )

    # Invalid confidence (too high)
    with pytest.raises(ValueError, match="outside \\[0.0, 1.0\\]"):
        Presupposition(
            trigger_word="know",
            trigger_type=TriggerType.FACTIVE_VERB,
            presupposed_content="test",
            confidence=1.5,
            segment_id="seg_001",
            speaker="Turkey",
        )

    # Invalid confidence (negative)
    with pytest.raises(ValueError, match="outside \\[0.0, 1.0\\]"):
        Presupposition(
            trigger_word="know",
            trigger_type=TriggerType.FACTIVE_VERB,
            presupposed_content="test",
            confidence=-0.1,
            segment_id="seg_001",
            speaker="Turkey",
        )


def test_presupposition_llm_confidence_validation():
    """Test LLM confidence validation."""
    # Valid LLM confidence
    Presupposition(
        trigger_word="know",
        trigger_type=TriggerType.FACTIVE_VERB,
        presupposed_content="test",
        confidence=0.5,
        segment_id="seg_001",
        speaker="Turkey",
        llm_confidence=0.9,
    )

    # Invalid LLM confidence
    with pytest.raises(ValueError, match="outside \\[0.0, 1.0\\]"):
        Presupposition(
            trigger_word="know",
            trigger_type=TriggerType.FACTIVE_VERB,
            presupposed_content="test",
            confidence=0.5,
            segment_id="seg_001",
            speaker="Turkey",
            llm_confidence=1.5,
        )


def test_presupposition_frozen():
    """Test that Presupposition model is frozen."""
    presup = Presupposition(
        trigger_word="know",
        trigger_type=TriggerType.FACTIVE_VERB,
        presupposed_content="test",
        confidence=0.5,
        segment_id="seg_001",
        speaker="Turkey",
    )

    # Should not be able to modify frozen model
    with pytest.raises(
        Exception
    ):  # Pydantic frozen models raise ValidationError on assignment
        presup.trigger_word = "realize"


def test_presupposition_extraction_result():
    """Test PresuppositionExtractionResult creation."""
    presup1 = Presupposition(
        trigger_word="know",
        trigger_type=TriggerType.FACTIVE_VERB,
        presupposed_content="test1",
        confidence=0.8,
        segment_id="seg_001",
        speaker="Turkey",
    )
    presup2 = Presupposition(
        trigger_word="regret",
        trigger_type=TriggerType.FACTIVE_VERB,
        presupposed_content="test2",
        confidence=0.9,
        segment_id="seg_002",
        speaker="Turkey",
    )

    result = PresuppositionExtractionResult(
        presuppositions=[presup1, presup2],
        total_triggers_found=5,
        verified_count=2,
        false_positive_filtered=3,
        processing_time_ms=150.5,
        language_detected="en",
    )

    assert len(result.presuppositions) == 2
    assert result.total_triggers_found == 5
    assert result.verified_count == 2
    assert result.false_positive_filtered == 3
    assert result.processing_time_ms == 150.5
    assert result.language_detected == "en"


def test_presupposition_extraction_result_precision_estimate():
    """Test precision estimate calculation."""
    presup = Presupposition(
        trigger_word="know",
        trigger_type=TriggerType.FACTIVE_VERB,
        presupposed_content="test",
        confidence=0.8,
        segment_id="seg_001",
        speaker="Turkey",
    )

    result = PresuppositionExtractionResult(
        presuppositions=[presup],
        total_triggers_found=5,
        verified_count=1,
        false_positive_filtered=4,
        processing_time_ms=100.0,
    )

    # precision = 1 / (1 + 4) = 0.2
    assert result.precision_estimate == 0.2


def test_presupposition_extraction_result_verification_rate():
    """Test verification rate calculation."""
    result = PresuppositionExtractionResult(
        presuppositions=[],
        total_triggers_found=10,
        verified_count=5,
        false_positive_filtered=5,
        processing_time_ms=100.0,
    )

    # verification_rate = 5 / 10 = 0.5
    assert result.verification_rate == 0.5


def test_trigger_type_enum():
    """Test TriggerType enum values."""
    assert TriggerType.FACTIVE_VERB.value == "FACTIVE_VERB"
    assert TriggerType.IMPLICATIVE_VERB.value == "IMPLICATIVE_VERB"
    assert TriggerType.TEMPORAL_ADVERB.value == "TEMPORAL_ADVERB"
    assert TriggerType.TEMPORAL_MULTIWORD.value == "TEMPORAL_MULTIWORD"
    assert TriggerType.CHANGE_OF_STATE.value == "CHANGE_OF_STATE"
    assert TriggerType.DEFINITE_NP.value == "DEFINITE_NP"
    assert TriggerType.CLEFT_CONSTRUCTION.value == "CLEFT_CONSTRUCTION"


def test_verification_method_enum():
    """Test VerificationMethod enum values."""
    assert VerificationMethod.RULE.value == "rule"
    assert VerificationMethod.LLM.value == "llm"
    assert VerificationMethod.HYBRID.value == "hybrid"
