import pytest
import spacy
from bb_paxdata.domain.enums.signal_type import SignalType
from bb_paxdata.infrastructure.nlp.risk_signal_detector import RiskSignalDetector


@pytest.fixture
def detector():
    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        # Fallback if model is not installed
        pytest.skip("spacy model en_core_web_sm not found")
    return RiskSignalDetector(nlp)


@pytest.mark.asyncio
async def test_red_line_detection(detector):
    text = "This behavior is unacceptable and crosses a red line."
    signals = await detector.detect(text, sentence_id="s1")

    red_lines = [s for s in signals if s.signal_type == SignalType.RED_LINE]
    assert len(red_lines) >= 1
    assert any("red line" in s.signal_text.lower() for s in red_lines)
    assert red_lines[0].escalation_multiplier == 1.5


@pytest.mark.asyncio
async def test_retaliation_detection(detector):
    text = "We reserve the right to take retaliatory sanctions."
    signals = await detector.detect(text, sentence_id="s2")

    ret = [s for s in signals if s.signal_type == SignalType.RETALIATION]
    assert len(ret) >= 1
    assert any(s.escalation_multiplier == 2.0 for s in ret)


@pytest.mark.asyncio
async def test_cheap_talk_vs_costly(detector):
    text = "We hope you will comply. We will take formal action if necessary."
    signals = await detector.detect(text, sentence_id="s3")

    cheap = [s for s in signals if s.signal_type == SignalType.CHEAP_TALK]
    costly = [s for s in signals if s.signal_type == SignalType.COSTLY_SIGNAL]

    assert len(cheap) >= 1
    assert len(costly) >= 1
    assert cheap[0].credibility_score < costly[0].credibility_score
