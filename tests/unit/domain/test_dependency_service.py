"""
Unit tests for DependencyService.
"""

from unittest.mock import MagicMock

import pytest
from bb_paxdata.domain.services.dependency import DependencyService


class TestDependencyService:
    @pytest.fixture
    def service(self) -> DependencyService:
        return DependencyService()

    def test_extract_triples_basic(self, service: DependencyService) -> None:
        """Test basic SVO extraction from a mock sentence."""
        # Setup mock tokens
        # "Turkey supports Ukraine"
        mock_turkey = MagicMock(
            text="Turkey",
            lemma_="Turkey",
            pos_="PROPN",
            dep_="nsubj",
            subtree=[MagicMock(text="Turkey")],
        )
        mock_supports = MagicMock(
            text="supports",
            lemma_="support",
            pos_="VERB",
            dep_="ROOT",
            children=[mock_turkey],
        )
        mock_ukraine = MagicMock(
            text="Ukraine",
            lemma_="Ukraine",
            pos_="PROPN",
            dep_="obj",
            subtree=[MagicMock(text="Ukraine")],
        )

        # Link them
        mock_supports.children = [mock_turkey, mock_ukraine]
        mock_turkey.subtree = [mock_turkey]
        mock_ukraine.subtree = [mock_ukraine]

        # Mock sentence
        mock_sent = MagicMock()
        mock_sent.__iter__.return_value = [mock_turkey, mock_supports, mock_ukraine]

        # Mock Doc
        mock_doc = MagicMock()
        mock_doc.sents = [mock_sent]

        # Execute
        triples = service.extract_triples(mock_doc)

        # Assert
        assert len(triples) == 1
        assert triples[0].subject_raw == "Turkey"
        assert triples[0].verb_lemma == "support"
        assert triples[0].object_raw == "Ukraine"
        assert triples[0].is_passive is False
        assert triples[0].is_negative is False

    def test_extract_triples_passive(self, service: DependencyService) -> None:
        """Test passive voice detection."""
        # "Ukraine is supported by Turkey"
        mock_ukraine = MagicMock(
            text="Ukraine",
            dep_="nsubj:pass",
            pos_="PROPN",
            subtree=[MagicMock(text="Ukraine")],
        )
        mock_is = MagicMock(text="is", dep_="aux:pass")
        mock_supported = MagicMock(
            text="supported", lemma_="support", dep_="ROOT", pos_="VERB"
        )
        mock_turkey = MagicMock(
            text="Turkey", dep_="obl", pos_="PROPN", subtree=[MagicMock(text="Turkey")]
        )

        mock_supported.children = [mock_ukraine, mock_is, mock_turkey]
        mock_ukraine.subtree = [mock_ukraine]
        mock_turkey.subtree = [mock_turkey]

        mock_sent = MagicMock()
        mock_sent.__iter__.return_value = [
            mock_ukraine,
            mock_is,
            mock_supported,
            mock_turkey,
        ]

        mock_doc = MagicMock()
        mock_doc.sents = [mock_sent]

        triples = service.extract_triples(mock_doc)

        assert len(triples) == 1
        assert triples[0].is_passive is True
        assert triples[0].verb_lemma == "support"

    def test_extract_triples_negative(self, service: DependencyService) -> None:
        """Test negation detection."""
        # "Turkey does not support war"
        mock_turkey = MagicMock(
            text="Turkey",
            dep_="nsubj",
            pos_="PROPN",
            subtree=[MagicMock(text="Turkey")],
        )
        mock_not = MagicMock(text="not", dep_="neg")
        mock_support = MagicMock(
            text="support", lemma_="support", dep_="ROOT", pos_="VERB"
        )
        mock_war = MagicMock(
            text="war", dep_="obj", pos_="NOUN", subtree=[MagicMock(text="war")]
        )

        mock_support.children = [mock_turkey, mock_not, mock_war]
        mock_turkey.subtree = [mock_turkey]
        mock_war.subtree = [mock_war]

        mock_sent = MagicMock()
        mock_sent.__iter__.return_value = [
            mock_turkey,
            mock_not,
            mock_support,
            mock_war,
        ]

        mock_doc = MagicMock()
        mock_doc.sents = [mock_sent]

        triples = service.extract_triples(mock_doc)

        assert len(triples) == 1
        assert triples[0].is_negative is True
