import pytest
from bb_paxdata.domain.enums import RiskLevel
from bb_paxdata.domain.models.analysis import Analysis
from bb_paxdata.domain.services.cross_anomaly_service import (
    CrossAnomalyService,
)
from bb_paxdata.domain.services.prompt_registry import PromptRegistry, PromptVersion
from bb_paxdata.infrastructure.repositories.analysis_repository import (
    AnalysisRepository,
    IntegrityError,
)


def test_risk_escalation_logic():
    """AI düşük risk dese bile anomali yüksekse riskin HIGH'a çekildiğini doğrula."""
    service = CrossAnomalyService()

    # AI Risk: 0.1 (LOW), Anomaly: 0.9 (CRITICAL)
    # Eski mantıkla composite = 0.1*0.6 + 0.9*0.4 = 0.42 (MEDIUM)
    # Yeni mantıkla escalation tetiklenmeli ve 0.65 (HIGH) olmalı.

    analysis = Analysis(source_text="Test", ai_risk_score=0.1, ai_sentiment_score=0.0)

    # Mocking anomaly score calculated in detect
    # We bypass detect()'s rule execution and call _determine_risk_level directly for unit test
    temp_analysis = analysis.model_copy(update={"anomaly_score": 0.9})
    risk_level = service._determine_risk_level(temp_analysis)

    assert risk_level == RiskLevel.HIGH


def test_missing_ai_fallback_logic():
    """AI verisi yoksa anomalinin tek başına karar verici olduğunu doğrula."""
    service = CrossAnomalyService()

    # AI yok, Anomaly: 0.5
    # composite = 0.5 * 1.0 (FALLBACK_WEIGHT) = 0.5
    # Thresholds: >=0.7 CRITICAL, >=0.4 HIGH, >0.0 MEDIUM
    analysis = Analysis(source_text="Test")  # has_ai_output = False

    # Anomali 0.5 iken HIGH bekliyoruz
    temp_analysis = analysis.model_copy(update={"anomaly_score": 0.5})
    assert service._determine_risk_level(temp_analysis) == RiskLevel.HIGH

    # Anomali 0.1 iken MEDIUM bekliyoruz
    temp_analysis = analysis.model_copy(update={"anomaly_score": 0.1})
    assert service._determine_risk_level(temp_analysis) == RiskLevel.MEDIUM


def test_prompt_integrity_validation():
    """Repository'nin hatalı prompt hash'i reddettiğini doğrula."""
    registry = PromptRegistry()
    pv = PromptVersion(
        prompt_id="test", version="v1", template="Hello {text}", description="test"
    )
    registry.register(pv)

    repo = AnalysisRepository(prompt_registry=registry)

    # Geçerli hash ile kaydet
    analysis_ok = Analysis(
        source_text="test", prompt_version="test@v1", prompt_hash=pv.template_hash
    )
    repo.save(analysis_ok)  # Hata fırlatmamalı

    # Hatalı hash ile kaydet
    analysis_fail = Analysis(
        source_text="test", prompt_version="test@v1", prompt_hash="wrong_hash"
    )

    with pytest.raises(IntegrityError):
        repo.save(analysis_fail)
