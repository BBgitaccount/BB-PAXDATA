import pytest
from bb_paxdata.infrastructure.container.service_container import ServiceContainer


@pytest.mark.asyncio
async def test_pipeline_risk_power_integration():
    container = ServiceContainer.get_instance()
    pipeline = container.pipeline

    text = (
        "The United States demands immediate compliance. "
        "We will not tolerate further delays — this is a red line. "
        "Under UN resolution 242, we are treaty-bound to take action, "
        "and all options are on the table."
    )

    result = await pipeline.run(
        text=text, speaker_country="USA", speaker_power_level=0.9
    )

    assert result.success
    analysis = result.analysis

    # Check risk signals
    assert len(analysis.risk_signals) > 0
    assert any(s.signal_type == "red_line" for s in analysis.risk_signals)
    assert any(s.signal_type == "retaliation" for s in analysis.risk_signals)

    # Check power index
    assert "USA" in analysis.power_indices
    usa_power = analysis.power_indices["USA"]
    assert usa_power.total_power_index > 0.0

    # Check escalated risk score
    # Note: ai_risk_score might be None if AI call fails or is mocked
    # but the escalated_risk_score property should still work.
    assert analysis.escalated_risk_score >= (analysis.ai_risk_score or 0.0)
