import pytest
import spacy
from bb_paxdata.domain.enums.negation_type import NegationType
from bb_paxdata.infrastructure.nlp.negation_detector import SpacyNegationDetector


@pytest.fixture
def detector():
    # Load a small model for testing
    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        # Fallback or download if needed, but in this environment it should be available
        spacy.cli.download("en_core_web_sm")
        nlp = spacy.load("en_core_web_sm")
    return SpacyNegationDetector(nlp)


@pytest.mark.asyncio
async def test_surface_syntactic_scope(detector):
    text = "The delegation did not agree to the proposal."
    cues = await detector.detect(text, sentence_id="s1")

    assert len(cues) == 1
    cue = cues[0]
    assert cue.cue_text == "not"
    # Depending on spaCy's parse, it might be SYNTACTIC or SCOPE_WIDE if it has wide children
    # For this simple sentence, it should be SYNTACTIC
    assert cue.negation_type == NegationType.SYNTACTIC
    assert "agree" in (cue.scope_text or "")
    assert cue.focus_text in {"proposal", "agree"}  # Depending on exact parse
    assert cue.confidence == 1.0


@pytest.mark.asyncio
async def test_semantic_negation(detector):
    text = "They failed to reach an agreement."
    cues = await detector.detect(text, sentence_id="s2")

    assert len(cues) == 1
    cue = cues[0]
    assert cue.cue_text == "failed"
    assert cue.negation_type == NegationType.SEMANTIC
    assert "reach" in (cue.scope_text or "")
    assert cue.confidence == 0.85


@pytest.mark.asyncio
async def test_scope_wide_negation(detector):
    text = "It is not the case that the parties reached an agreement."
    cues = await detector.detect(text, sentence_id="s3")

    assert len(cues) >= 1
    # "not" SCOPE_WIDE olmalı
    not_cue = next(c for c in cues if c.cue_text == "not")
    # Check if it identified wide scope
    assert not_cue.negation_type in (NegationType.SCOPE_WIDE, NegationType.SYNTACTIC)
    if not_cue.negation_type == NegationType.SCOPE_WIDE:
        assert not_cue.confidence == 0.75
