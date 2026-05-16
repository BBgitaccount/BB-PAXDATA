# tests/unit/application/test_episodic_thematic.py
import pytest
import spacy
from bb_paxdata.application.pipeline.frame.episodic_themetic_classifier import (
    EpisodicThematicClassifier,
)
from bb_paxdata.domain.enums.frame_type import FrameType
from bb_paxdata.domain.models.segment import Segment


@pytest.fixture
def nlp():
    return spacy.load("en_core_web_sm")


@pytest.fixture
def classifier(nlp):
    return EpisodicThematicClassifier(nlp)


@pytest.mark.asyncio
async def test_classify_episodic(classifier):
    from bb_paxdata.domain.models.sentence import Sentence

    sentences = [
        Sentence(
            id="s1",
            text="Yesterday, a violent incident occurred during the border meeting.",
        ),
        Sentence(id="s2", text="The attack happened at 10 AM."),
    ]
    segment = Segment(id="test1", sentences=sentences)
    result = await classifier.classify(segment)
    assert result == FrameType.EPISODIC


@pytest.mark.asyncio
async def test_classify_thematic(classifier):
    from bb_paxdata.domain.models.sentence import Sentence

    sentences = [
        Sentence(
            id="s3",
            text="The systemic structural issues in the regional security architecture are chronic and pervasive.",
        ),
        Sentence(
            id="s4",
            text="Historically, democracy and sovereignty have been the pillars of diplomacy.",
        ),
    ]
    segment = Segment(id="test2", sentences=sentences)
    result = await classifier.classify(segment)
    assert result == FrameType.THEMATIC


@pytest.mark.asyncio
async def test_empty_text(classifier):
    segment = Segment(id="test3", sentences=[])
    with pytest.raises(ValueError):
        await classifier.classify(segment)
