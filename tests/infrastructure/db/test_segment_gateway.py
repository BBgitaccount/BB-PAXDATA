from unittest.mock import Mock

import pytest

from bb_paxdata.infrastructure.db.models import Sentence
from bb_paxdata.infrastructure.db.segment_enrichment_gateway import (
    SegmentEnrichmentGateway,
)


def test_enrichment_gateway_aggregates_entities():
    gateway = SegmentEnrichmentGateway()

    # Mock Sentence objects with various entities
    sentences = [
        Sentence(
            sent_id="sent_1",
            text="Erdoğan (Turkey) went to UN in USA.",
            entities_gpe=["Turkey", "USA"],
            entities_person=["Erdoğan"],
            entities_org=["UN"],
        ),
        Sentence(
            sent_id="sent_2",
            text="NATO discussed security with UK.",
            entities_gpe=["UK", "Turkey"],
            entities_person=[],
            entities_org=["NATO"],
        ),
    ]

    entities = gateway._aggregate_entities(sentences)
    assert set(entities["GPE"]) == {"Turkey", "USA", "UK"}
    assert set(entities["ORG"]) == {"UN", "NATO"}
    assert set(entities["PERSON"]) == {"Erdoğan"}


def test_enrichment_gateway_resolves_dominant_frame_ai_priority():
    gateway = SegmentEnrichmentGateway()

    sentences = [
        Sentence(sent_id="sent_1", text="text 1", dominant_frame="CONFLICT_FRAME"),
        Sentence(sent_id="sent_2", text="text 2", dominant_frame="PEACE_FRAME"),
    ]

    # Mock pipeline_res with frame_salience
    mock_fs = Mock()
    mock_fs.dominant_frame = Mock()
    mock_fs.dominant_frame.value = "NEGOTIATION_FRAME"

    mock_pipeline_res = Mock()
    mock_pipeline_res.analysis = Mock()
    mock_pipeline_res.analysis.frame_salience = mock_fs

    dominant = gateway._resolve_dominant_frame(sentences, mock_pipeline_res)
    assert dominant == "NEGOTIATION_FRAME"


def test_enrichment_gateway_resolves_dominant_frame_rules_fallback():
    gateway = SegmentEnrichmentGateway()

    sentences = [
        Sentence(sent_id="sent_1", text="text 1", dominant_frame="CONFLICT_FRAME"),
        Sentence(sent_id="sent_2", text="text 2", dominant_frame="PEACE_FRAME"),
        Sentence(sent_id="sent_3", text="text 3", dominant_frame="CONFLICT_FRAME"),
    ]

    dominant = gateway._resolve_dominant_frame(sentences, pipeline_res=None)
    assert dominant == "CONFLICT_FRAME"


def test_enrichment_gateway_calculates_demand_concentration():
    gateway = SegmentEnrichmentGateway()

    sentences = [
        Sentence(sent_id="sent_1", text="must 1", demand_type="reform"),
        Sentence(sent_id="sent_2", text="normal 2", demand_type=None),
        Sentence(sent_id="sent_3", text="must 3", demand_type="security"),
        Sentence(sent_id="sent_4", text="normal 4", demand_type=None),
        Sentence(sent_id="sent_5", text="must 5", demand_type="reform"),
    ]

    # Total 5 sentences:
    # intro: sentences[:1] (sent_1) -> has demand -> 1
    # concl: sentences[4:] (sent_5) -> has demand -> 1
    # develop: sentences[1:4] (sent_2, sent_3, sent_4) -> sent_3 has demand -> 1
    conc = gateway._calculate_demand_concentration(sentences)
    assert conc == {"intro": 1, "develop": 1, "concl": 1}


def test_enrichment_gateway_calculates_inconsistency():
    gateway = SegmentEnrichmentGateway()

    sentences = [
        Mock(discrepancy_score=0.2, formula_inconsistency_score=0.0),
        Mock(discrepancy_score=0.0, formula_inconsistency_score=0.4),
        Mock(discrepancy_score=0.0, formula_inconsistency_score=0.6),
    ]

    inconsistency = gateway._calculate_inconsistency(sentences)
    assert pytest.approx(inconsistency) == 0.4
