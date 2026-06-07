"""
Unit tests for presupposition service.
"""

from unittest.mock import AsyncMock, Mock

import pytest
from bb_paxdata.application.domain.lexicons.presupposition_triggers import (
    PresuppositionLexicon,
)
from bb_paxdata.application.domain.models.presupposition import (
    PresuppositionExtractionResult,
    TriggerType,
)
from bb_paxdata.application.domain.services.presupposition_service import (
    PresuppositionService,
)
from bb_paxdata.application.domain.services.presupposition_verifier import (
    PresuppositionVerifier,
)


@pytest.fixture
def mock_verifier():
    """Create a mock PresuppositionVerifier."""
    verifier = Mock(spec=PresuppositionVerifier)
    verifier.verify_batch = AsyncMock(return_value=[])
    return verifier


@pytest.fixture
def mock_negation_detector():
    """Create a mock negation detector."""
    detector = Mock()
    detector.detect_with_doc = AsyncMock(return_value=Mock(cues=[], has_negation=False))
    return detector


@pytest.fixture
def presupposition_service(mock_verifier, mock_negation_detector):
    """Create a PresuppositionService instance."""
    lexicon = PresuppositionLexicon.load_default()
    return PresuppositionService(
        verifier=mock_verifier,
        lexicon=lexicon,
        negation_detector=mock_negation_detector,
        llm_confidence_threshold=0.85,
        use_llm_verification=False,  # Disable LLM for unit tests
    )


def test_service_initialization(presupposition_service):
    """Test that PresuppositionService initializes correctly."""
    assert presupposition_service._verifier is not None
    assert presupposition_service._lexicon is not None
    assert presupposition_service._negation_detector is not None
    assert presupposition_service._llm_confidence_threshold == 0.85
    assert presupposition_service._use_llm_verification is False


@pytest.mark.asyncio
async def test_extract_with_empty_doc(presupposition_service):
    """Test extraction with a document containing no triggers."""
    # Create a mock spaCy Doc with no triggers
    mock_doc = Mock()
    mock_doc.text = "Hello world, this is a test."
    mock_doc.__iter__ = Mock(return_value=iter([]))

    result = await presupposition_service.extract(
        doc=mock_doc,
        segment_id="seg_001",
        speaker="TestSpeaker",
        language="en",
    )

    assert isinstance(result, PresuppositionExtractionResult)
    assert len(result.presuppositions) == 0
    assert result.total_triggers_found == 0


def test_helper_find_subject():
    """Test find_subject helper function."""
    service = PresuppositionService(
        verifier=Mock(),
        lexicon=PresuppositionLexicon.load_default(),
        negation_detector=Mock(),
    )

    # Create mock tokens
    mock_token = Mock()
    mock_token.children = []
    mock_token.head = Mock()
    mock_token.head.pos_ = "VERB"
    mock_token.head.children = []

    # Test with no subject
    result = service._find_subject(mock_token, Mock())
    assert result == ""


def test_helper_find_object():
    """Test find_object helper function."""
    service = PresuppositionService(
        verifier=Mock(),
        lexicon=PresuppositionLexicon.load_default(),
        negation_detector=Mock(),
    )

    mock_token = Mock()
    mock_token.children = []

    result = service._find_object(mock_token, Mock())
    assert result == ""


def test_helper_extract_that_clause():
    """Test extract_that_clause helper function."""
    service = PresuppositionService(
        verifier=Mock(),
        lexicon=PresuppositionLexicon.load_default(),
        negation_detector=Mock(),
    )

    mock_token = Mock()
    mock_token.children = []

    result = service._extract_that_clause(mock_token, Mock())
    assert result == ""


def test_calculate_base_confidence():
    """Test confidence calculation."""
    service = PresuppositionService(
        verifier=Mock(),
        lexicon=PresuppositionLexicon.load_default(),
        negation_detector=Mock(),
    )

    mock_token = Mock()
    mock_token.lemma_ = "know"
    mock_token.sent = Mock()
    mock_token.sent.__len__ = Mock(return_value=5)

    confidence = service._calculate_base_confidence(
        mock_token, TriggerType.FACTIVE_VERB, "test content"
    )

    # "know" has specificity 0.60
    # confidence = 0.5 + (0.60 * 0.2) + (1.0 * 0.2) + (0.5 * 0.1) = 0.5 + 0.12 + 0.2 + 0.05 = 0.87
    assert 0.0 <= confidence <= 1.0


def test_calculate_base_confidence_high_specificity():
    """Test confidence calculation with high specificity trigger."""
    service = PresuppositionService(
        verifier=Mock(),
        lexicon=PresuppositionLexicon.load_default(),
        negation_detector=Mock(),
    )

    mock_token = Mock()
    mock_token.lemma_ = "regret"
    mock_token.sent = Mock()
    mock_token.sent.__len__ = Mock(return_value=5)

    confidence = service._calculate_base_confidence(
        mock_token, TriggerType.FACTIVE_VERB, "test content"
    )

    # "regret" has specificity 0.90
    # confidence = 0.5 + (0.90 * 0.2) + (1.0 * 0.2) + (0.5 * 0.1) = 0.5 + 0.18 + 0.2 + 0.05 = 0.93
    assert 0.0 <= confidence <= 1.0
    assert confidence > 0.9  # Should be higher than "know"


def test_is_known_entity():
    """Test is_known_entity helper."""
    service = PresuppositionService(
        verifier=Mock(),
        lexicon=PresuppositionLexicon.load_default(),
        negation_detector=Mock(),
    )

    mock_doc = Mock()
    mock_ent = Mock()
    mock_ent.text = "Turkey"
    mock_doc.ents = [mock_ent]

    assert service._is_known_entity("Turkey", mock_doc) is True
    assert service._is_known_entity("Germany", mock_doc) is False
