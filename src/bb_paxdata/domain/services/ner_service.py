# ============================================================
# DOSYA: src/bb_paxdata/domain/services/ner_service.py
# AÇIKLAMA: spaCy tabanlı NER + diplomatik gazetteer
# ============================================================

from __future__ import annotations

import logging
from typing import Any

import spacy
import spacy.cli
from spacy.language import Language

from .language_detector import LanguageDetector

logger = logging.getLogger(__name__)

# Diplomatik terminoloji için kural tabanlı genişletici
DIPLOMATIC_GAZETTEER: dict[str, list[str]] = {
    "ORG": [
        "BM",
        "Birleşmiş Milletler",
        "United Nations",
        "AB",
        "Avrupa Birliği",
        "European Union",
        "NATO",
        "OECD",
        "DTÖ",
        "Dünya Ticaret Örgütü",
        "World Trade Organization",
        "İMF",
        "Uluslararası Para Fonu",
        "IMF",
        "D8",
        "G20",
        "G7",
        "AGİT",
        "OSCE",
        "İslam İşbirliği Teşkilatı",
        "OIC",
        "Türk Devletleri Teşkilatı",
        "Organisation of Turkic States",
        "Dünya Bankası",
        "World Bank",
    ],
    "GPE": [
        "Türkiye",
        "Ankara",
        "İstanbul",
        "Türkiye Cumhuriyeti",
        "Washington",
        "Brüksel",
        "Moskova",
        "Pekin",
        "Beijing",
        "Tokyo",
        "Berlin",
        "Paris",
        "Londra",
        "London",
        "Riyad",
        "Kahire",
        "Tahran",
    ],
    "EVENT": [
        "zirve",
        "summit",
        "müzakere",
        "negotiation",
        "anlaşma",
        "agreement",
        "mutabakat",
        "accord",
        "bildirge",
        "declaration",
        "antlaşma",
        "treaty",
        "görüşme",
        "talks",
        "konferans",
        "conference",
    ],
}


class SpacyNERService:
    """
    Gerçek NER servisi — spaCy tabanlı, çok dilli.
    Diplomatik gazetteer ile spaCy'nin kaçırdığı terimleri yakalar.
    Model yoksa otomatik indirir.
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
                logger.info(f"spaCy NER modeli yüklendi: {model_name}")
            except OSError:
                logger.warning(f"spaCy modeli bulunamadı, indiriliyor: {model_name}")
                try:
                    spacy.cli.download(model_name)  # type: ignore[attr-defined]
                    self._models[lang] = spacy.load(model_name)
                    logger.info(f"spaCy modeli indirildi ve yüklendi: {model_name}")
                except (Exception, SystemExit) as e:
                    logger.error(f"spaCy modeli indirilemedi ({model_name}): {e}")

    def extract(self, text: str, language: str | None = None) -> dict[str, Any]:
        language = language or self.language_detector.detect(text)
        nlp = self._models.get(language) or self._models.get("en")

        entities: list[dict[str, Any]] = []

        if nlp is not None:
            doc = nlp(text)
            seen_spans: set[tuple[int, int]] = set()

            for ent in doc.ents:
                entities.append(
                    {
                        "text": ent.text,
                        "label": ent.label_,
                        "start": ent.start_char,
                        "end": ent.end_char,
                        "source": "spacy",
                    }
                )
                seen_spans.add((ent.start_char, ent.end_char))

            # Gazetteer tabanlı genişletme
            for label, terms in DIPLOMATIC_GAZETTEER.items():
                for term in terms:
                    start = 0
                    while True:
                        idx = text.lower().find(term.lower(), start)
                        if idx == -1:
                            break
                        end_idx = idx + len(term)
                        if not any(
                            s <= idx < e or s < end_idx <= e for s, e in seen_spans
                        ):
                            entities.append(
                                {
                                    "text": text[idx:end_idx],
                                    "label": label,
                                    "start": idx,
                                    "end": end_idx,
                                    "source": "gazetteer",
                                }
                            )
                            seen_spans.add((idx, end_idx))
                        start = idx + 1
        else:
            logger.error(
                "Hiçbir spaCy modeli yüklü değil, boş NER sonucu döndürülüyor."
            )

        return {"entities": entities, "language": language}
