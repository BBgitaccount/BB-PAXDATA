import pytest
import spacy
from bb_paxdata.infrastructure.nlp.power_index_calculator import PowerIndexCalculator


@pytest.fixture
def calculator():
    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        pytest.skip("spacy model en_core_web_sm not found")
    return PowerIndexCalculator(nlp)


@pytest.mark.asyncio
async def test_authority_markers(calculator):
    text = "We demand immediate withdrawal. It is imperative that all parties comply."
    idx = await calculator.calculate(text, "speaker1", "seg1")

    assert idx.authority_markers > 0.0
    assert idx.total_power_index > 0.0


@pytest.mark.asyncio
async def test_legitimation_strategies(calculator):
    text = (
        "Under international law and UN resolution 242, we have an obligation to act."
    )
    idx = await calculator.calculate(text, "speaker2", "seg2")

    assert idx.legitimation_strategies > 0.0
    assert "un resolution" in text.lower()
