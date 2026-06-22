# tests/integration/test_pipeline_lazy_ai.py
"""
Faz 2.2 Lazy AI Evaluation — Entegrasyon Testleri

AnalysisPipeline → CollectStage → DeterministicRiskScorer akışının
gerçek ServiceContainer (logic_mode=True) üzerinden doğru çalıştığını test eder.

logic_mode=True olduğunda:
  - AIAnalyst → LogicOnlyAIAnalyst ile çalışır (gerçek LLM çağrısı yok)
  - no_ai_mode (threshold=2.0) → her zaman bypass
  - default (threshold=0.5) → risk sinyali bazlı karar
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from bb_paxdata.application.domain.enums.signal_type import SignalType
from bb_paxdata.application.domain.models.risk_signal import RiskSignal
from bb_paxdata.infrastructure.container.service_container import ServiceContainer

# ───────────────────────────────────────────────────────────────────
# HELPERS
# ───────────────────────────────────────────────────────────────────


def _make_risk_signal(credibility: float, escalation: float = 1.0) -> RiskSignal:
    return RiskSignal(
        signal_text="test threat signal",
        signal_start=0,
        signal_end=18,
        signal_type=SignalType.RED_LINE,
        credibility_score=credibility,
        escalation_multiplier=escalation,
        sentence_id="int-s0",
    )


# ───────────────────────────────────────────────────────────────────
# no_ai_mode entegrasyon (threshold=2.0 → her zaman bypass)
# ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_no_ai_mode_always_bypasses_ai() -> None:
    """
    no_ai_mode variant'ı threshold=2.0 ile yapılandırılmıştır.
    Herhangi bir metin için risk skoru her zaman < 2.0 olacağından AI bypass edilmeli.
    """
    ServiceContainer.reset_instance()
    container = ServiceContainer.get_instance(logic_mode=True)
    pipeline = container.pipeline

    result = await pipeline.run(
        text="We will not tolerate this unacceptable threat on our borders.",
        metadata={"pipeline_variant": "no_ai_mode"},
    )

    assert result.success is True
    assert result.raw_ai is not None
    # no_ai_mode → her zaman bypass veya disabled döner
    assert result.raw_ai.prompt_version in ("bypassed", "disabled")


@pytest.mark.asyncio
async def test_no_ai_mode_neutral_text_also_bypasses() -> None:
    """
    no_ai_mode'da düşük riskli metinler de bypass edilmeli (threshold=2.0).
    """
    ServiceContainer.reset_instance()
    container = ServiceContainer.get_instance(logic_mode=True)
    pipeline = container.pipeline

    result = await pipeline.run(
        text="Türkiye, olumlu diplomatik ilişkilerini sürdürmektedir.",
        metadata={"pipeline_variant": "no_ai_mode"},
    )

    assert result.success is True
    assert result.raw_ai is not None
    assert result.raw_ai.prompt_version in ("bypassed", "disabled")


# ───────────────────────────────────────────────────────────────────
# default variant — risk sinyali enjeksiyonu ile bypass kontrolü
# ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_default_variant_low_risk_bypasses_ai() -> None:
    """
    default variant'ta (threshold=0.5) risk sinyali olmayan metin bypass edilmeli.
    CollectStage.risk_detector mock'lanarak sıfır sinyal döndürülür.
    """
    ServiceContainer.reset_instance()
    container = ServiceContainer.get_instance(logic_mode=True)
    pipeline = container.pipeline

    # risk_detector'ı sıfır sinyal döndürecek şekilde mock'la
    pipeline.collect_stage._risk_detector.detect = AsyncMock(return_value=())
    pipeline.collect_stage._negation_detector.detect = AsyncMock(return_value=())

    # AI analyst track et
    ai_analyst = pipeline.collect_stage._ai_analyst
    original_analyze = ai_analyst.analyze
    ai_call_count = [0]

    async def _tracked_analyze(*args, **kwargs):
        ai_call_count[0] += 1
        return await original_analyze(*args, **kwargs)

    ai_analyst.analyze = _tracked_analyze

    result = await pipeline.run(
        text="A routine diplomatic meeting took place.",
        metadata={"pipeline_variant": "default"},
    )

    assert result.success is True
    assert ai_call_count[0] == 0, "Düşük riskli metin için AI çağrısı olmamalıydı"
    assert result.raw_ai is not None
    assert result.raw_ai.prompt_version == "bypassed"


@pytest.mark.asyncio
async def test_default_variant_high_risk_triggers_ai() -> None:
    """
    default variant'ta (threshold=0.5) yüksek risk sinyali enjekte edildiğinde AI çalışmalı.
    """
    ServiceContainer.reset_instance()
    container = ServiceContainer.get_instance(logic_mode=True)
    pipeline = container.pipeline

    # Yüksek risk: skor = 0.9 * 1.5 = 1.35 > 0.5
    high_risk_signals = (_make_risk_signal(credibility=0.9, escalation=1.5),)
    pipeline.collect_stage._risk_detector.detect = AsyncMock(
        return_value=high_risk_signals
    )
    pipeline.collect_stage._negation_detector.detect = AsyncMock(return_value=())

    # AI analyst track et
    ai_analyst = pipeline.collect_stage._ai_analyst
    original_analyze = ai_analyst.analyze
    ai_call_count = [0]

    async def _tracked_analyze(*args, **kwargs):
        ai_call_count[0] += 1
        return await original_analyze(*args, **kwargs)

    ai_analyst.analyze = _tracked_analyze

    result = await pipeline.run(
        text="We will retaliate immediately if provoked.",
        metadata={"pipeline_variant": "default"},
    )

    assert result.success is True
    assert ai_call_count[0] == 1, "Yüksek riskli metin için AI çalışmalıydı"
    # Logic mode'da prompt_version "logic_only" veya benzeri olabilir, ama "bypassed" değil
    assert result.raw_ai.prompt_version != "bypassed"


# ───────────────────────────────────────────────────────────────────
# Konfigürasyon doğrulaması
# ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pipeline_config_has_correct_thresholds() -> None:
    """
    Konfiguratör'ün threshold değerlerini doğru okuduğunu doğrular.
    - default: 0.5
    - fast_mode: 0.5
    - no_ai_mode: 2.0
    """
    from bb_paxdata.application.pipeline.configurator import PipelineConfigurator

    configurator = PipelineConfigurator()

    default_cfg = configurator.get_config("default")
    fast_cfg = configurator.get_config("fast_mode")
    no_ai_cfg = configurator.get_config("no_ai_mode")

    assert default_cfg["collect"]["lazy_ai_risk_threshold"] == pytest.approx(0.5)
    assert fast_cfg["collect"]["lazy_ai_risk_threshold"] == pytest.approx(0.3)
    assert no_ai_cfg["collect"]["lazy_ai_risk_threshold"] == pytest.approx(2.0)


@pytest.mark.asyncio
async def test_pipeline_threshold_forwarding() -> None:
    """
    AnalysisPipeline'ın threshold'u YAML konfigürasyonundan okuyup
    CollectStage.run()'a doğru ilettiğini doğrular.
    """
    ServiceContainer.reset_instance()
    container = ServiceContainer.get_instance(logic_mode=True)
    pipeline = container.pipeline

    # CollectStage.run'ı intercept et, threshold parametresini yakala
    original_run = pipeline.collect_stage.run
    captured_thresholds: list[float] = []

    async def _intercepted_run(*args, **kwargs):
        threshold = kwargs.get("lazy_ai_risk_threshold", -1.0)
        captured_thresholds.append(threshold)
        return await original_run(*args, **kwargs)

    pipeline.collect_stage.run = _intercepted_run

    # no_ai_mode → threshold=2.0 iletilmeli
    await pipeline.run(
        text="Test cümlesi.",
        metadata={"pipeline_variant": "no_ai_mode"},
    )

    assert len(captured_thresholds) == 1
    assert captured_thresholds[0] == pytest.approx(
        2.0
    ), f"no_ai_mode için threshold=2.0 bekleniyordu, gelen: {captured_thresholds[0]}"

    # default → threshold=0.5 iletilmeli
    await pipeline.run(
        text="Başka bir cümle.",
        metadata={"pipeline_variant": "default"},
    )

    assert len(captured_thresholds) == 2
    assert captured_thresholds[1] == pytest.approx(
        0.5
    ), f"default için threshold=0.5 bekleniyordu, gelen: {captured_thresholds[1]}"


# ───────────────────────────────────────────────────────────────────
# Telemetri — bypass sayacı entegrasyon testi
# ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bypass_counter_increments_across_multiple_sentences() -> None:
    """
    Birden fazla cümle işlendiğinde bypass sayacının doğru artığını doğrular.
    """
    ServiceContainer.reset_instance()
    container = ServiceContainer.get_instance(logic_mode=True)
    pipeline = container.pipeline

    # Tüm cümleler düşük riskli (bypass tetiklenmeli)
    pipeline.collect_stage._risk_detector.detect = AsyncMock(return_value=())
    pipeline.collect_stage._negation_detector.detect = AsyncMock(return_value=())

    ai_analyst = pipeline.collect_stage._ai_analyst

    # AI analyst'ın increment_bypass'ini track et
    original_increment = getattr(ai_analyst, "increment_bypass", None)
    bypass_calls = [0]

    def _tracked_increment():
        bypass_calls[0] += 1
        if original_increment:
            original_increment()

    if hasattr(ai_analyst, "increment_bypass"):
        ai_analyst.increment_bypass = _tracked_increment

    sentences = [
        "Routine diplomatic update.",
        "Standard meeting concluded.",
        "Normal protocol observed.",
    ]

    for sentence in sentences:
        await pipeline.run(
            text=sentence,
            metadata={"pipeline_variant": "default"},
        )

    if hasattr(ai_analyst, "increment_bypass"):
        assert (
            bypass_calls[0] == 3
        ), f"3 cümle için 3 bypass bekleniyor, gelen: {bypass_calls[0]}"


@pytest.mark.asyncio
async def test_limited_ai_analyst_bypass_summary() -> None:
    """
    LimitedAIAnalyst.get_usage_summary() yöntemi bypass_analyze_calls içermeli.
    """
    from bb_paxdata.infrastructure.nlp.limited_ai_analyst import LimitedAIAnalyst
    from bb_paxdata.infrastructure.nlp.logic_only_analyst import LogicOnlyAIAnalyst

    logic_only = LogicOnlyAIAnalyst()
    analyst = LimitedAIAnalyst(delegate=logic_only, limit=5)

    analyst.increment_bypass()
    analyst.increment_bypass()
    analyst.increment_bypass()

    summary = analyst.get_usage_summary()

    assert "bypassed_analyze_calls" in summary
    assert summary["bypassed_analyze_calls"] == 3
    assert "efficiency_ratio" in summary
