# tests/application/services/test_aggregation_engine.py
from datetime import datetime

import numpy as np
import pytest

from bb_paxdata.application.services.aggregation_engine import AggregationEngine
from bb_paxdata.infrastructure.db.models import SegmentAnalyzedEvent


def test_calculate_bootstrap_ci_standard():
    engine = AggregationEngine(n_bootstrap_iterations=100)
    values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    weights = np.array([1.0, 1.0, 1.0, 1.0, 1.0])

    lower, upper, std_dev = engine.calculate_bootstrap_ci(values, weights)

    assert lower <= 3.0 <= upper
    assert lower < upper
    assert std_dev > 0.0


def test_calculate_bootstrap_ci_small_sample():
    engine = AggregationEngine(n_bootstrap_iterations=100)
    values = np.array([1.5, 3.5])
    weights = np.array([1.0, 1.0])

    lower, upper, std_dev = engine.calculate_bootstrap_ci(values, weights)

    # n < 3 fallback should trigger
    assert lower == 2.5
    assert upper == 2.5
    assert std_dev == 0.0


def test_calculate_bootstrap_ci_empty():
    engine = AggregationEngine(n_bootstrap_iterations=100)
    values = np.array([])
    weights = np.array([])

    lower, upper, std_dev = engine.calculate_bootstrap_ci(values, weights)
    assert lower == 0.0
    assert upper == 0.0
    assert std_dev == 0.0


def test_calculate_entropy():
    engine = AggregationEngine()

    # Uniform distribution (2 classes) -> H = 1.0
    h_uniform = engine.calculate_entropy([0.5, 0.5])
    assert pytest.approx(h_uniform) == 1.0

    # Pure distribution -> H = 0.0
    h_pure = engine.calculate_entropy([1.0, 0.0])
    assert pytest.approx(h_pure) == 0.0


def test_calculate_js_divergence():
    engine = AggregationEngine()

    p = [0.8, 0.2]
    q = [0.8, 0.2]
    jsd_identical = engine.calculate_js_divergence(p, q)
    assert pytest.approx(jsd_identical) == 0.0

    p2 = [1.0, 0.0]
    q2 = [0.0, 1.0]
    jsd_disjoint = engine.calculate_js_divergence(p2, q2)
    assert 0.0 < jsd_disjoint <= 1.0


def test_aggregate_events_success():
    engine = AggregationEngine(n_bootstrap_iterations=50)

    # Construct mock events
    event_tr = SegmentAnalyzedEvent(
        event_id="ev-tr-1",
        event_timestamp=datetime.now(),
        file_id="file_001",
        segment_id="seg-1",
        country="TR",
        text_snippet="Turkey urges security and economic stability",
        vader_compound=0.5,
        diplo_compound=0.6,
        vad_vector={"V": 0.6, "A": 0.5, "D": 0.5},
        emotion_category="constructive",
        risk_score=2.0,
        demand_count=1,
        speech_act="ASSERTIVE",
        hedging_score=0.2,
        politeness_ratio=0.8,
        topic_scores={"topic_1": 0.8, "topic_2": 0.2},
        topic_model_version="v1",
        frame_distribution={
            "security": 0.5,
            "economic": 0.5,
            "legal": 0.0,
            "humanitarian": 0.0,
        },
        pipeline_run_id="run_001",
        power_level=5,
    )

    event_uk = SegmentAnalyzedEvent(
        event_id="ev-uk-1",
        event_timestamp=datetime.now(),
        file_id="file_001",
        segment_id="seg-2",
        country="UK",
        text_snippet="UK agrees on economic security measures",
        vader_compound=0.4,
        diplo_compound=0.5,
        vad_vector={"V": 0.55, "A": 0.45, "D": 0.5},
        emotion_category="constructive",
        risk_score=3.0,
        demand_count=0,
        speech_act="ASSERTIVE",
        hedging_score=0.3,
        politeness_ratio=0.7,
        topic_scores={"topic_1": 0.75, "topic_2": 0.25},
        topic_model_version="v1",
        frame_distribution={
            "security": 0.6,
            "economic": 0.4,
            "legal": 0.0,
            "humanitarian": 0.0,
        },
        pipeline_run_id="run_001",
        power_level=4,
    )

    event_us = SegmentAnalyzedEvent(
        event_id="ev-us-1",
        event_timestamp=datetime.now(),
        file_id="file_001",
        segment_id="seg-3",
        country="US",
        text_snippet="US demands different priorities",
        vader_compound=-0.2,
        diplo_compound=-0.3,
        vad_vector={"V": 0.4, "A": 0.6, "D": 0.6},
        emotion_category="concerned",
        risk_score=6.0,
        demand_count=3,
        speech_act="DIRECTIVE",
        hedging_score=0.4,
        politeness_ratio=0.5,
        topic_scores={"topic_1": 0.3, "topic_2": 0.7},
        topic_model_version="v1",
        frame_distribution={
            "security": 0.2,
            "economic": 0.8,
            "legal": 0.0,
            "humanitarian": 0.0,
        },
        pipeline_run_id="run_001",
        power_level=3,
    )

    events = [event_tr, event_uk, event_us]

    projections, documents = engine.aggregate_events(events)

    # 3 countries * 2 topics = 6 projections
    assert len(projections) == 6
    assert len(documents) == 3

    # Find TR topic_1 projection
    tr_t1 = next(p for p in projections if p.country == "TR" and p.topic == "topic_1")
    assert tr_t1.score == 0.8
    assert tr_t1.risk_score == 2.0
    assert tr_t1.composite_risk_index == pytest.approx(1.6)
    assert tr_t1.avg_sentiment == 0.6
    assert tr_t1.dominant_emotion == "constructive"
    assert tr_t1.dominant_frame == "security"
    assert tr_t1.avg_vad is not None
    assert tr_t1.avg_vad["V"] == 0.6

    # TR and UK are highly aligned (cosine similarity close to 1.0)
    # Check coalition mapping
    assert "UK" in tr_t1.top_coalition_actors
    assert "US" not in tr_t1.top_coalition_actors

    # Check document properties
    doc_tr = next(d for d in documents if d.country == "TR")
    assert doc_tr.topic_model_version == "v1"
    assert "topic_1" in doc_tr.topic_details
    assert "topic_2" in doc_tr.topic_details
    assert doc_tr.diplomatic_tension_index > 0.0
