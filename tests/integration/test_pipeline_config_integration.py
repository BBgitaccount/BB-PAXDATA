import pytest
from bb_paxdata.infrastructure.container.service_container import ServiceContainer


@pytest.mark.asyncio
async def test_pipeline_integration_default_variant() -> None:
    """Test that the default variant runs all stages including consensus."""
    ServiceContainer.reset_instance()
    container = ServiceContainer.get_instance(logic_mode=True)
    pipeline = container.pipeline

    result = await pipeline.run(
        text="Türkiye Ukrayna'yı destekliyor.", metadata={"pipeline_variant": "default"}
    )

    assert result.success is True
    # Default variant runs 'dual_gate' consensus
    assert result.analysis.consensus_result is not None
    assert result.analysis.coherence_score is not None


@pytest.mark.asyncio
async def test_pipeline_integration_fast_mode_variant() -> None:
    """Test that fast_mode disables dual_gate consensus."""
    ServiceContainer.reset_instance()
    container = ServiceContainer.get_instance(logic_mode=True)
    pipeline = container.pipeline

    result = await pipeline.run(
        text="Türkiye Ukrayna'yı destekliyor.",
        metadata={"pipeline_variant": "fast_mode"},
    )

    assert result.success is True
    # fast_mode does not run 'dual_gate', so consensus_result remains None
    assert result.analysis.consensus_result is None
    assert result.analysis.coherence_score is None


@pytest.mark.asyncio
async def test_pipeline_integration_no_ai_mode_variant() -> None:
    """Test that no_ai_mode skips AI analysis and populates default disabled status."""
    ServiceContainer.reset_instance()
    container = ServiceContainer.get_instance(logic_mode=True)
    pipeline = container.pipeline

    result = await pipeline.run(
        text="Türkiye Ukrayna'yı destekliyor.",
        metadata={"pipeline_variant": "no_ai_mode"},
    )

    assert result.success is True
    assert result.raw_ai is not None
    assert result.raw_ai.prompt_version == "disabled"
    assert "disabled" in result.raw_ai.error
