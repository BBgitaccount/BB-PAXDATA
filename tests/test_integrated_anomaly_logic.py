import pytest

from bb_paxdata.application.domain.models.analysis import Analysis
from bb_paxdata.application.domain.services.cross_anomaly_service import (
    EntityFlipRule,
    ToneDriftRule,
)
from bb_paxdata.infrastructure.container.service_container import ServiceContainer


@pytest.mark.asyncio
async def test_integrated_anomaly_rules_logic():
    # 1. Reset and initialize ServiceContainer in logic-only mode
    ServiceContainer.reset_instance()
    container = ServiceContainer.get_instance(logic_mode=True)
    pipeline = container.pipeline

    # Verify container is in logic-only mode
    assert container._logic_mode is True

    # 2. Test ToneDriftRule directly
    tone_rule = ToneDriftRule(sigma_multiplier=1.0, min_sentences=3)

    # Analysis with high sentiment variance (drift)
    # Sentence 1: Neutral, Sentence 2: Extremely Positive, Sentence 3: Extremely Negative
    analysis_drift = Analysis(
        source_text="Normal negotiations. This is wonderful! I hate this.",
        sentences=["Normal negotiations.", "This is wonderful!", "I hate this."],
    )
    triggered, score, msg = tone_rule.evaluate(analysis_drift)
    assert triggered is True
    assert score > 0.0
    assert "TONE_DRIFT" in msg

    # Analysis with no drift (stable sentiment)
    analysis_stable = Analysis(
        source_text="Normal day. All is well. Nothing to report.",
        sentences=["Normal day.", "All is well.", "Nothing to report."],
    )
    triggered, score, msg = tone_rule.evaluate(analysis_stable)
    assert triggered is False

    # 3. Test EntityFlipRule directly
    flip_rule = EntityFlipRule(flip_threshold=0.8)

    # Analysis with contradictory sentiment on entity "Turkey"
    # Sentence 1: Turkey is cooperative (positive), Sentence 2: Turkey is aggressive (negative)
    analysis_flip = Analysis(
        source_text="We appreciate Turkey. Turkey has launched a threat.",
        sentences=["We appreciate Turkey.", "Turkey has launched a threat."],
        entities=[
            {"text": "Turkey", "label": "GPE"},
            {"text": "Turkey", "label": "GPE"},
        ],
    )
    triggered, score, msg = flip_rule.evaluate(analysis_flip)
    assert triggered is True
    assert score > 0.0
    assert "ENTITY_FLIP" in msg

    # 4. Run pipeline.run in logic-only mode to verify end-to-end flow doesn't crash
    text = "We appreciate Turkey. Turkey has launched a threat. This is wonderful! I hate this."
    result = await pipeline.run(
        text=text,
        file_id="test_panel_1",
        speaker_country="Turkey",
    )
    assert result.success is True
    assert result.analysis.anomaly_score is not None
    assert len(result.analysis.anomaly_flags) > 0

    # Cleanup container instance
    ServiceContainer.reset_instance()
