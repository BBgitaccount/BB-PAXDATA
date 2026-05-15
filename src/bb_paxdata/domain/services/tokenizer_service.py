from __future__ import annotations

import logging
from typing import Any

import spacy
import spacy.cli
from spacy.language import Language

from .language_detector import LanguageDetector

logger = logging.getLogger(__name__)


class SpacyTokenizerService:
    """
    Gerçek tokenizer servisi — spaCy tabanlı, çok dilli.
    spaCy yüklenemezse basit boşluk tokenizasyonu fallback'i devreye girer.
    """

    def __init__(
        self,
        model_map: dict[str, str] | None = None,
        language_detector: LanguageDetector | None = None,
    ):
        self.language_detector = language_detector or LanguageDetector()
        self._model_map = model_map or {
            "tr": "tr_core_news_sm",
            "en": "en_core_web_sm",
        }
        self._models: dict[str, Language] = {}
        self._ensure_models()

    def _ensure_models(self) -> None:
        for lang, model_name in self._model_map.items():
            try:
                self._models[lang] = spacy.load(model_name)
            except OSError:
                try:
                    spacy.cli.download(model_name)  # type: ignore[attr-defined]
                    self._models[lang] = spacy.load(model_name)
                except (Exception, SystemExit) as e:
                    logger.error(f"Tokenizer modeli indirilemedi ({model_name}): {e}")

    async def tokenize(self, text: str, language: str | None = None) -> dict[str, Any]:
        language = language or self.language_detector.detect(text)
        nlp = self._models.get(language) or self._models.get("en")

        if nlp is None:
            # Fallback: basit boşluk tokenizasyonu
            logger.warning(
                "spaCy modeli yok — basit tokenizasyon fallback'i devreye girdi."
            )
            tokens = text.split()
            return {
                "tokens": tokens,
                "sentences": [text],
                "sentence_count": 1,
                "language": language,
            }

        doc = nlp(text)
        tokens = [token.text for token in doc if not token.is_space]
        sentences = [sent.text.strip() for sent in doc.sents if sent.text.strip()]

        return {
            "tokens": tokens,
            "sentences": sentences,
            "sentence_count": len(sentences),
            "language": language,
        }
