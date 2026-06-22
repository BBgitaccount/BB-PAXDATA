import pytest
import spacy

from bb_paxdata.application.domain.enums import NegationType
from bb_paxdata.application.domain.models.negation_cue import LanguageCode
from bb_paxdata.infrastructure.nlp.negation_detector import SpacyNegationDetector


@pytest.fixture(scope="module")
def nlp_tr():
    try:
        return spacy.load("tr_core_news_md")
    except OSError:
        spacy.cli.download("tr_core_news_md")
        return spacy.load("tr_core_news_md")


@pytest.fixture
def detector(nlp_tr):
    return SpacyNegationDetector(nlp_tr=nlp_tr)


@pytest.mark.asyncio
class TestTurkishNegation:
    async def test_surface_degil(self, detector):
        result = await detector.detect("Bu iddia doğru değil.", "s1", language="tr")
        assert result.has_negation is True
        cue = result.cues[0]
        assert cue.cue_text == "değil"
        assert cue.negation_type == NegationType.SURFACE
        assert "doğru" in cue.scope_tokens  # "değil" öncesini scope alır

    async def test_morphological_mez(self, detector):
        result = await detector.detect(
            "Türkiye bu şartları kabul etmez.", "s2", language="tr"
        )
        assert result.has_negation is True
        morph_cues = [
            c for c in result.cues if c.negation_type == NegationType.SYNTACTIC
        ]
        assert len(morph_cues) >= 1
        assert "etmez" in [c.cue_text for c in morph_cues]

    async def test_suffix_siz(self, detector):
        result = await detector.detect("Güvensiz bir bölgedeyiz.", "s3", language="tr")
        assert result.has_negation is True
        sem_cues = [c for c in result.cues if c.negation_type == NegationType.SEMANTIC]
        assert any("siz" in c.cue_text for c in sem_cues)

    async def test_compound_negation(self, detector):
        result = await detector.detect(
            "Hiçbir şekilde kabul etmeyeceğiz.", "s4", language="tr"
        )
        assert result.has_negation is True
        compound = [c for c in result.cues if c.negation_type == NegationType.COMPOUND]
        assert len(compound) >= 1 or len(result.cues) >= 2

    async def test_language_auto_detection(self, detector):
        """Türkçe karakterler varsa auto-detect TR."""
        result = await detector.detect("Bu doğru değil.", "s6")  # language=None
        assert result.cues[0].language == LanguageCode.TR

    async def test_empty_no_negation(self, detector):
        result = await detector.detect(
            "Barışçıl bir görüşme yapıldı.", "s7", language="tr"
        )
        assert result.has_negation is False
        assert result.cues == []
