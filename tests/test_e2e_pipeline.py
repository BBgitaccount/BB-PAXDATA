# ============================================================
# DOSYA: tests/test_e2e_pipeline.py
# AÇIKLAMA: 4 kritik hatanın çözümünü doğrulayan uçtan uca test
# ============================================================

from unittest.mock import MagicMock

import pytest
from bb_paxdata.application.pipeline.analysis_pipeline import (
    AnalysisPipeline,
    PipelineResult,
)
from bb_paxdata.application.pipeline.assembler import AnalysisAssembler
from bb_paxdata.domain.models.ai_analysis import AIAnalysisResult
from bb_paxdata.domain.models.analysis import Analysis
from bb_paxdata.domain.services.ai_analyst import AIAnalyst
from bb_paxdata.domain.services.cross_anomaly_service import CrossAnomalyService
from bb_paxdata.domain.services.prompt_registry import build_default_registry


class TestAnalysisModel:
    """HATA 1: Analysis modeli AI alanlarını içermeli ve property'ler çalışmalı."""

    def test_analysis_has_ai_fields(self):
        a = Analysis(source_text="Test", ai_sentiment_score=-0.5, ai_risk_score=0.7)
        assert a.ai_sentiment_score == -0.5
        assert a.ai_risk_score == 0.7
        assert a.has_ai_output is True
        assert a.effective_sentiment == -0.5
        assert a.effective_risk == 0.7

    def test_analysis_none_safety(self):
        """None AI değerleri 0.0 değil None kalmalı; effective_ property 0.0 dönmeli."""
        a = Analysis(source_text="Test")
        assert a.ai_sentiment_score is None
        assert a.ai_risk_score is None
        assert a.has_ai_output is False
        assert a.effective_sentiment == 0.0
        assert a.effective_risk == 0.0

    def test_analysis_pydantic_validation(self):
        """Geçersiz skor değerleri ValidationError fırlatmalı."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            Analysis(source_text="Test", ai_sentiment_score=2.0)  # Max 1.0


class TestCrossAnomalyService:
    """HATA 1: CrossAnomalyService getattr kullanmıyor, AnomalyResult döndürüyor."""

    def setup_method(self):
        self.service = CrossAnomalyService()

    def test_no_getattr_usage(self):
        """Servis analysis.effective_risk kullanmalı, 0.0 sabit dönmemeli."""
        a = Analysis(source_text="Test", ai_sentiment_score=0.5, ai_risk_score=0.9)
        result = self.service.detect(a)
        assert result.score > 0.0  # Gerçek AI skorları görülüyor

    def test_divergence_rule_triggered(self):
        """Pozitif duygu + yüksek risk → DIVERGENCE anomalisi tetiklenmeli."""
        a = Analysis(source_text="Test", ai_sentiment_score=0.5, ai_risk_score=0.85)
        result = self.service.detect(a)
        assert result.score > 0.0
        assert len(result.flags) > 0
        assert any("DIVERGENCE" in flag or "RISK" in flag for flag in result.flags)

    def test_no_fake_anomaly_without_ai_output(self):
        """AI çıktısı yoksa sahte anomali üretilmemeli."""
        a = Analysis(source_text="Test")
        result = self.service.detect(a)
        assert result.score == 0.0
        assert any("NO_AI_OUTPUT" in flag for flag in result.flags)

    def test_returns_anomaly_result_not_analysis(self):
        """detect() Analysis mutate etmemeli, AnomalyResult döndürmeli."""
        from bb_paxdata.domain.services.cross_anomaly_service import AnomalyResult

        a = Analysis(source_text="Test", ai_sentiment_score=-0.8, ai_risk_score=0.85)
        result = self.service.detect(a)
        assert isinstance(result, AnomalyResult)
        assert a.anomaly_score is None  # Orijinal nesne mutate edilmedi!


class TestAnalysisAssembler:
    """HATA 2: Assembler dict → Analysis dönüşümü yapmalı."""

    def setup_method(self):
        self.assembler = AnalysisAssembler()

    def test_assembler_converts_to_analysis(self):
        ai_result = AIAnalysisResult(
            sentiment_score=-0.6,
            risk_score=0.75,
            sentiment_label="negative",
            risk_factors=["crisis"],
            summary="Acil toplantı",
            key_claims=["Kritik durum"],
            prompt_version="diplomatic_analysis@v2.1",
            prompt_hash="a1b2c3d4e5f6a7b8",
            model_name="gpt-4o",
        )
        result = self.assembler.assemble(
            source_text="BM Güvenlik Konseyi acil toplandı.",
            language="tr",
            ner_result={"entities": [{"text": "BM", "label": "ORG"}]},
            tokenizer_result={
                "tokens": ["BM", "Konseyi"],
                "sentence_count": 1,
                "sentences": ["BM Güvenlik Konseyi acil toplandı."],
            },
            ai_result=ai_result,
        )
        assert isinstance(result, Analysis)
        assert result.ai_sentiment_score == -0.6
        assert result.ai_risk_score == 0.75
        assert result.prompt_version == "diplomatic_analysis@v2.1"
        assert result.prompt_hash == "a1b2c3d4e5f6a7b8"
        assert result.language == "tr"


class TestPromptRegistry:
    """HATA 4: Prompt versiyonlama çalışmalı, her çıktı prompt bilgisini taşımalı."""

    def setup_method(self):
        self.registry = build_default_registry()
        self.analyst = AIAnalyst(registry=self.registry)

    def test_active_version_exists(self):
        active = self.registry.get_active("diplomatic_analysis")
        assert active is not None
        assert active.is_active is True

    def test_ai_result_has_prompt_version_stamp(self):
        result = self.analyst.analyze("Test metni")
        assert result.prompt_version is not None
        assert "@" in result.prompt_version
        assert result.prompt_version != "diplomatic_analysis@unknown"

    def test_prompt_hash_present(self):
        result = self.analyst.analyze("Test metni")
        assert result.prompt_hash is not None
        assert len(result.prompt_hash) == 16  # SHA256'nın ilk 16 karakteri

    def test_rollback_changes_active_version(self):
        self.registry.activate("diplomatic_analysis", "v1.0")
        # v1.0 is 'en', so we must specify 'en' or change it to 'any'
        active = self.registry.get_active("diplomatic_analysis", language="en")
        assert active is not None
        assert active.version == "v1.0"
        # Geri al
        self.registry.activate("diplomatic_analysis", "v2.1")


class TestPipelineIntegration:
    """HATA 2 + 3: Pipeline uçtan uca çalışmalı, immutable data flow korunmalı."""

    def setup_method(self):
        registry = build_default_registry()
        self.ai_analyst = AIAnalyst(registry=registry)
        self.anomaly_service = CrossAnomalyService()
        self.assembler = AnalysisAssembler()

        from bb_paxdata.domain.services.ner_service import SpacyNERService
        from bb_paxdata.domain.services.tokenizer_service import SpacyTokenizerService

        self.ner_service = SpacyNERService()
        self.tokenizer_service = SpacyTokenizerService()

        self.pipeline = AnalysisPipeline(
            ner_service=self.ner_service,
            tokenizer_service=self.tokenizer_service,
            ai_analyst=self.ai_analyst,
            anomaly_service=self.anomaly_service,
            assembler=self.assembler,
        )

    def test_full_e2e_diplomatic_mixed_text(self):
        """Türkçe-İngilizce karma diplomatik metin tam pipeline'dan geçmeli."""
        text = "NATO zirvesinde Türkiye ve ABD arasında diplomatik gerilim yaşandı."
        result = self.pipeline.run(text)

        assert isinstance(result, PipelineResult)
        assert isinstance(result.analysis, Analysis)
        assert result.analysis.source_text == text
        assert result.analysis.tokens is not None
        assert result.analysis.entities is not None
        assert result.analysis.prompt_version is not None
        assert "@" in result.analysis.prompt_version
        assert result.analysis.anomaly_score is not None

    def test_immutability_preserved(self):
        """DETECT aşaması orijinal Analysis nesnesini mutate etmemeli."""
        text = "Kriz büyüyor."
        result = self.pipeline.run(text)
        # raw_ai içindeki orijinal AIAnalysisResult etkilenmemiş olmalı
        if result.raw_ai:
            assert result.raw_ai.sentiment_score == result.analysis.ai_sentiment_score

    def test_analyze_sentence_alias_works(self):
        """Geriye uyumlu alias çalışmalı."""
        text = "Müzakereler başarısız oldu."
        result1 = self.pipeline.run(text)
        result2 = self.pipeline.analyze_sentence(text)
        assert isinstance(result1, type(result2))

    def test_fail_fast_mode(self):
        """fail_fast_on_missing_ai=True ile AI çıktısı yoksa hata rapor edilmeli."""
        mock_ai = MagicMock()
        mock_ai.analyze.return_value = AIAnalysisResult(
            prompt_version="test@v1",
            # sentiment_score ve risk_score None → has_ai_output=False
        )

        pipeline_strict = AnalysisPipeline(
            ner_service=self.ner_service,
            tokenizer_service=self.tokenizer_service,
            ai_analyst=mock_ai,
            anomaly_service=self.anomaly_service,
            assembler=self.assembler,
            fail_fast_on_missing_ai=True,
        )
        result = pipeline_strict.run("Test metni")
        assert any("MISSING_AI" in err for err in result.errors)
