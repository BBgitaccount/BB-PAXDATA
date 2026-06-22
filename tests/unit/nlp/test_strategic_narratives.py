# tests/unit/nlp/test_strategic_narratives.py
"""
TASK-A05: Strategic Narrative Analysis — Unit Test Suite
=========================================================
Coverage:
  1. NarrativeSalienceTracker.compute_salience()             — score ordering & bounds
  2. NarrativeSalienceTracker.calculate_speech_act_modifier() — coercive boost isolation
  3. NarrativeClassifierStage.classify_segment_layer()       — layer assignment + None fallback
  4. NarrativeClassifierStage.process_analysis()             — bilateral enrichment end-to-end
  5. CrossAnomalyServiceImpl.detect_narrative_clashes()       — anomaly trigger (async)
"""

import pytest

from bb_paxdata.application.domain.enums.country_enums import NarrativeLayer
from bb_paxdata.application.domain.enums.frame_type import FrameType
from bb_paxdata.application.domain.models.analysis import Analysis
from bb_paxdata.application.domain.models.bilateral_sentiment import BilateralSentiment
from bb_paxdata.application.domain.models.frame_annotation import FrameSalienceResult
from bb_paxdata.application.domain.models.speech_act import (
    SpeechActClassification,
    SpeechActType,
)
from bb_paxdata.application.domain.services.narrative_salience_tracker import (
    NarrativeSalienceTracker,
)
from bb_paxdata.application.pipeline.stages.narrative_classifier_stage import (
    NarrativeClassifierStage,
)
from bb_paxdata.infrastructure.nlp.cross_anomaly_service_impl import (
    CrossAnomalyServiceImpl,
)

# ──────────────────────────────────────────────────────────────
# TEST 1: Salience score ordering & bounds
# ──────────────────────────────────────────────────────────────


def test_narrative_salience_calculation():
    """ASSERTIVE gets no modifier; DIRECTIVE+coercive must outscore it."""
    tracker = NarrativeSalienceTracker(speech_act_weight=0.25, sigmoid_scale=1.5)

    frame_salience = FrameSalienceResult(
        segment_id="seg-1",
        salience_scores={FrameType.PROBLEM_DEFINITION: 0.8},
        dominant_frame=FrameType.PROBLEM_DEFINITION,
        is_competitive=False,
        competing_frames=[],
    )

    # Case 1: ASSERTIVE — modifier stays at 1.0 (no boost)
    speech_act_assertive = SpeechActClassification(
        primary_type=SpeechActType.ASSERTIVE, confidence=0.8, force_modifier=None
    )
    score_1 = tracker.compute_salience(
        base_frequency=1, frame_salience=frame_salience, speech_act=speech_act_assertive
    )

    # Case 2: DIRECTIVE + coercive force_modifier → additional +0.15 on top of directive boost
    speech_act_coercive = SpeechActClassification(
        primary_type=SpeechActType.DIRECTIVE, confidence=0.9, force_modifier="strongly"
    )
    score_2 = tracker.compute_salience(
        base_frequency=1, frame_salience=frame_salience, speech_act=speech_act_coercive
    )

    assert score_2 > score_1, "Coercive DIRECTIVE must outscore plain ASSERTIVE"
    assert 0.0 <= score_1 <= 1.0
    assert 0.0 <= score_2 <= 1.0


# ──────────────────────────────────────────────────────────────
# TEST 2: Coercive boost isolated (FINDING P-02)
# ──────────────────────────────────────────────────────────────


def test_narrative_salience_coercive_boost_isolated():
    """Verify coercive boost is exactly +0.15 independent of salience pipeline."""
    tracker = NarrativeSalienceTracker(speech_act_weight=0.25, sigmoid_scale=1.5)

    directive_base = SpeechActClassification(
        primary_type=SpeechActType.DIRECTIVE, confidence=0.9, force_modifier=None
    )
    directive_coercive = SpeechActClassification(
        primary_type=SpeechActType.DIRECTIVE, confidence=0.9, force_modifier="strongly"
    )

    mod_base = tracker.calculate_speech_act_modifier(directive_base)
    mod_coercive = tracker.calculate_speech_act_modifier(directive_coercive)

    assert (
        abs(mod_coercive - mod_base - 0.15) < 1e-9
    ), f"Expected coercive boost of exactly 0.15, got delta={mod_coercive - mod_base:.9f}"


# ──────────────────────────────────────────────────────────────
# TEST 3: Narrative layer classification (FINDING P-06)
# ──────────────────────────────────────────────────────────────


def test_narrative_classifier_layer_assignment():
    """Each canonical text must map to the correct NarrativeLayer; zero-signal → None."""
    tracker = NarrativeSalienceTracker()
    stage = NarrativeClassifierStage(tracker=tracker)

    sys_text = "The UN Charter is the foundation of rules-based multipolar world order."
    ident_text = "It is our national interest and historic duty to protect sovereignty."
    issue_text = (
        "We call for a ceasefire violation inquiry along the gas pipeline corridor."
    )
    empty_sig = "Today is a sunny day in the city center."  # No narrative keywords

    assert stage.classify_segment_layer(sys_text) == NarrativeLayer.SYSTEM
    assert stage.classify_segment_layer(ident_text) == NarrativeLayer.IDENTITY
    assert stage.classify_segment_layer(issue_text) == NarrativeLayer.ISSUE
    assert (
        stage.classify_segment_layer(empty_sig) is None
    ), "Zero-signal text must return None, not default to ISSUE (FINDING P-06)"


# ──────────────────────────────────────────────────────────────
# TEST 4: Pipeline stage enrichment end-to-end (FINDING P-01)
# ──────────────────────────────────────────────────────────────


def test_narrative_classifier_stage_process_analysis():
    """NarrativeClassifierStage must enrich BilateralSentiment objects in-place via model_copy."""
    tracker = NarrativeSalienceTracker()
    stage = NarrativeClassifierStage(tracker=tracker)

    bilateral = BilateralSentiment(
        panel_id="panel-123",
        from_country="Turkey",
        to_country="Greece",
        avg_sentiment=-0.4,
        total_mentions=5,
    )

    analysis = Analysis(
        source_text="It is our national interest and historic duty to protect sovereignty.",
        speaker_id="Turkey",
        entities=[{"text": "Greece", "label": "GPE"}],
        bilateral_metrics=[bilateral],
    )

    enriched = stage.process_analysis(analysis)

    assert len(enriched.bilateral_metrics) == 1
    metric = enriched.bilateral_metrics[0]
    assert (
        metric.narrative_layer == NarrativeLayer.IDENTITY
    ), "IDENTITY keywords must yield NarrativeLayer.IDENTITY on the bilateral metric"
    assert (
        metric.narrative_target_actor == "Greece"
    ), "GPE entity 'Greece' must be resolved as narrative_target_actor"
    assert (
        metric.narrative_salience > 0.0
    ), "Salience must be non-zero for matched IDENTITY keywords"


# ──────────────────────────────────────────────────────────────
# TEST 5: Anomaly clash trigger (FINDING I-01, I-02)
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio(loop_scope="function")
async def test_narrative_clash_anomaly_trigger():
    """detect_narrative_clashes() must fire when avg_sentiment<-0.3 AND IDENTITY salience>0.6."""
    service = CrossAnomalyServiceImpl()

    bilateral = BilateralSentiment(
        panel_id="panel-123",
        from_country="Turkey",
        to_country="Greece",
        avg_sentiment=-0.4,  # Hostile context (< -0.3 threshold)
        total_mentions=5,
    )
    bilateral = bilateral.model_copy(
        update={
            "narrative_layer": NarrativeLayer.IDENTITY,
            "narrative_salience": 0.8,  # > 0.6 threshold
        }
    )

    analysis = Analysis(
        id="anal-1",
        source_text="This is an identity defense statement.",
        bilateral_metrics=[bilateral],
    )

    result = await service.detect_narrative_clashes(analysis, threshold=0.3)

    assert result.is_anomaly is True, "Should be flagged as anomaly"
    assert result.metadata["narrative_clash"] is True
    assert "STRATEGIC NARRATIVE CLASH" in result.metadata["description"]
    # Verify non-zero metadata counts (FINDING I-01)
    assert result.n_sentences >= 0
    assert result.m1 == 0.8  # clash_salience captured
    assert result.m2 == 1.0  # 1 bilateral with IDENTITY layer
    assert result.score > 0.0
