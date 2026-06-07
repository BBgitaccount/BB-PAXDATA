import pytest
import spacy
from bb_paxdata.application.domain.enums.negation_type import NegationType
from bb_paxdata.infrastructure.nlp.negation_detector import SpacyNegationDetector


@pytest.fixture
def detector():
    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        spacy.cli.download("en_core_web_sm")
        nlp = spacy.load("en_core_web_sm")
    return SpacyNegationDetector(nlp)


@pytest.mark.asyncio
async def test_surface_syntactic_scope(detector):
    text = "The delegation did not agree to the proposal."
    result = await detector.detect(text, sentence_id="s1")
    cues = result.cues

    assert len(cues) == 1
    cue = cues[0]
    assert cue.cue_text == "not"
    # Depending on spaCy's parse, it should be SURFACE or SYNTACTIC
    assert cue.negation_type in (NegationType.SYNTACTIC, NegationType.SURFACE)
    assert cue.confidence == 1.0


@pytest.mark.asyncio
async def test_semantic_negation(detector):
    text = "They failed to reach an agreement."
    result = await detector.detect(text, sentence_id="s2")
    cues = result.cues

    assert len(cues) == 1
    cue = cues[0]
    assert cue.cue_text == "failed"
    assert cue.negation_type == NegationType.SEMANTIC
    assert cue.confidence == 0.85


@pytest.mark.asyncio
async def test_scope_wide_negation(detector):
    text = "It is not the case that the parties reached an agreement."
    result = await detector.detect(text, sentence_id="s3")
    cues = result.cues

    assert len(cues) >= 1
    not_cue = next(c for c in cues if c.cue_text == "not")
    assert not_cue.negation_type in (
        NegationType.SCOPE_WIDE,
        NegationType.SYNTACTIC,
        NegationType.SURFACE,
    )
