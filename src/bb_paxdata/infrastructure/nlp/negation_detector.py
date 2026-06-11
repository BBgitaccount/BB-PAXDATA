import asyncio
import logging
from typing import Any

import spacy
from spacy.language import Language

from bb_paxdata.application.domain.enums.negation_type import NegationType
from bb_paxdata.application.domain.models.negation_cue import (
    LanguageCode,
    NegationCue,
    NegationResult,
)

logger = logging.getLogger(__name__)


class SpacyNegationDetector:
    """
    Dil-agnostik ve Türkçe odaklı negasyon tespiti.
    spaCy morph ve dependency parse ağaçlarından yararlanır.
    """

    # İngilizce Kuralları
    EN_SURFACE_CUES = frozenset(
        {
            "not",
            "n't",
            "never",
            "no",
            "none",
            "nobody",
            "nothing",
            "neither",
            "nor",
            "nowhere",
            "hardly",
            "scarcely",
            "barely",
            "without",
        }
    )
    EN_SEMANTIC_CUES = frozenset(
        {
            "fail",
            "deny",
            "refuse",
            "reject",
            "avoid",
            "prevent",
            "lack",
            "absence",
            "decline",
            "oppose",
        }
    )

    # Türkçe Kuralları
    TR_SURFACE_CUES = frozenset(
        {"değil", "yok", "hiç", "hiçbir", "asla", "katiyen", "bir türlü"}
    )
    TR_SEMANTIC_SUFFIXES = ("sız", "siz", "suz", "süz")

    def __init__(
        self,
        nlp: Language | None = None,
        nlp_en: Language | None = None,
        nlp_tr: Language | None = None,
    ):
        self._models: dict[LanguageCode, Language] = {}
        if nlp:
            lang_meta = nlp.meta.get("lang", "en")
            if lang_meta == "tr":
                self._models[LanguageCode.TR] = nlp
            else:
                self._models[LanguageCode.EN] = nlp
        if nlp_en:
            self._models[LanguageCode.EN] = nlp_en
        if nlp_tr:
            self._models[LanguageCode.TR] = nlp_tr

    async def detect(
        self, text: str, sentence_id: str, language: str | None = None
    ) -> NegationResult:
        """Entry point. Language is auto-detected if not explicitly provided."""
        lang = self._resolve_language(text, language)
        nlp = self._get_model(lang)

        doc = await self._spacy_parse_async(nlp, text)
        return await self.detect_with_doc(doc, sentence_id, lang)

    async def detect_with_doc(
        self, doc: Any, sentence_id: str, language: LanguageCode
    ) -> NegationResult:
        """Parse tree üzerinden negasyon tespiti."""
        cues: list[NegationCue] = []

        for token in doc:
            cue = self._detect_cue(token, sentence_id, language)
            if cue:
                cues.append(cue)

        # Scope tespiti (dil spesifik)
        cues = self._resolve_scopes(doc, cues, language)

        # Compound negasyon tespiti
        cues = self._detect_compound_negation(cues, language)

        # Dominant scope hesapla
        dominant = max(
            (c.scope_tokens for c in cues if c.scope_tokens), key=len, default=()
        )

        return NegationResult(
            cues=cues,
            has_negation=len(cues) > 0,
            dominant_scope=dominant,
        )

    # ── Internal Methods ──
    def _resolve_language(self, text: str, hint: str | None) -> LanguageCode:
        if hint in ("tr", "tur"):
            return LanguageCode.TR
        if hint in ("en", "eng"):
            return LanguageCode.EN
        # Basit heuristic: Türkçe karakter var mı?
        if any(c in text for c in "çğıöşüÇĞİÖŞÜ"):
            return LanguageCode.TR
        return LanguageCode.EN

    def _get_model(self, lang: LanguageCode) -> Language:
        if lang not in self._models:
            if lang == LanguageCode.TR:
                logger.info("Loading Turkish spaCy model...")
                try:
                    self._models[lang] = spacy.load("tr_core_news_md")
                except OSError:
                    import subprocess
                    import sys

                    subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "pip",
                            "install",
                            "https://huggingface.co/turkish-nlp-suite/tr_core_news_md/resolve/main/tr_core_news_md-1.0-py3-none-any.whl",
                        ],
                        check=True,
                    )
                    self._models[lang] = spacy.load("tr_core_news_md")
            else:
                logger.info("Loading English spaCy model...")
                try:
                    self._models[lang] = spacy.load("en_core_web_md")
                except OSError:
                    try:
                        self._models[lang] = spacy.load("en_core_web_sm")
                    except OSError:
                        spacy.cli.download("en_core_web_sm")
                        self._models[lang] = spacy.load("en_core_web_sm")
        return self._models[lang]

    async def _spacy_parse_async(self, nlp: Language, text: str) -> Any:
        """CPU-bound spaCy parsing'i thread pool'a offload et."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, nlp, text)

    def _detect_cue(
        self, token: Any, sentence_id: str, lang: LanguageCode
    ) -> NegationCue | None:
        """Token-level negasyon tespiti."""
        if lang == LanguageCode.TR:
            return self._detect_tr_cue(token, sentence_id)
        return self._detect_en_cue(token, sentence_id)

    def _detect_tr_cue(self, token: Any, sentence_id: str) -> NegationCue | None:
        """Türkçe negasyon tespiti: Sözcüksel + Morfolojik + Suffix."""
        lower = token.lower_

        # 1. Sözcüksel (Lexical) negasyon
        if lower in self.TR_SURFACE_CUES:
            scope = self._tr_surface_scope(token, lower)
            return NegationCue(
                cue_text=token.text,
                cue_start=token.idx,
                cue_end=token.idx + len(token.text),
                negation_type=NegationType.SURFACE,
                sentence_id=sentence_id,
                language=LanguageCode.TR,
                scope_tokens=scope,
                confidence=1.0,
            )

        # 2. Morfolojik negasyon (spaCy morph + robust lemma-suffix pattern matching)
        morph_polarity = token.morph.get("Polarity")
        is_neg = morph_polarity and "Neg" in morph_polarity

        # Robust suffix-pattern fallback if spaCy lemmatizer/morph parser misses Polarity=Neg
        if not is_neg and token.pos_ in ("VERB", "AUX"):
            text_lower = token.text.lower()
            neg_patterns = (
                "mey",
                "may",
                "med",
                "mad",
                "mes",
                "mas",
                "mez",
                "maz",
                "miy",
                "mıy",
                "muy",
                "müy",
                "meme",
                "mama",
            )
            if any(pat in text_lower for pat in neg_patterns):
                is_neg = True
            elif text_lower.endswith(("ma", "me")):
                is_neg = True

        if is_neg:
            scope = self._tr_morphological_scope(token)
            return NegationCue(
                cue_text=token.text,
                cue_start=token.idx,
                cue_end=token.idx + len(token.text),
                negation_type=NegationType.SYNTACTIC,
                sentence_id=sentence_id,
                language=LanguageCode.TR,
                scope_tokens=scope,
                confidence=0.95,  # Morph/suffix match has high confidence
            )

        # 3. Yokluk ekleri (-sız/-siz)
        if len(lower) > 3 and lower.endswith(self.TR_SEMANTIC_SUFFIXES):
            scope = self._tr_suffix_scope(token)
            return NegationCue(
                cue_text=token.text[-3:],  # Sadece ek
                cue_start=token.idx + len(token.text) - 3,
                cue_end=token.idx + len(token.text),
                negation_type=NegationType.SEMANTIC,
                sentence_id=sentence_id,
                language=LanguageCode.TR,
                scope_tokens=scope,
                confidence=0.8,
            )

        return None

    def _detect_en_cue(self, token: Any, sentence_id: str) -> NegationCue | None:
        """İngilizce negasyon tespiti."""
        lower = token.lower_

        if lower in self.EN_SURFACE_CUES:
            return NegationCue(
                cue_text=token.text,
                cue_start=token.idx,
                cue_end=token.idx + len(token.text),
                negation_type=NegationType.SURFACE,
                sentence_id=sentence_id,
                language=LanguageCode.EN,
                scope_tokens=self._en_surface_scope(token),
                confidence=1.0,
            )

        if lower in self.EN_SEMANTIC_CUES or token.lemma_ in self.EN_SEMANTIC_CUES:
            return NegationCue(
                cue_text=token.text,
                cue_start=token.idx,
                cue_end=token.idx + len(token.text),
                negation_type=NegationType.SEMANTIC,
                sentence_id=sentence_id,
                language=LanguageCode.EN,
                scope_tokens=(),
                confidence=0.85,
            )

        return None

    # ── Turkish Scope Resolution ──
    def _tr_surface_scope(self, token: Any, cue_word: str) -> tuple[str, ...]:
        """Türkçe sözcüksel negasyonun etki alanı."""
        if cue_word == "değil":
            if token.i > 0:
                prev_tokens = [t.text for t in token.doc[: token.i]]
                return tuple(prev_tokens)
        return tuple(t.text for t in token.sent)

    def _tr_morphological_scope(self, token: Any) -> tuple[str, ...]:
        """Morfolojik negasyonun etki alanı (fiilin subtree'ı)."""
        subtree = list(token.subtree)
        if subtree:
            return tuple(t.text for t in subtree)
        return tuple(t.text for t in token.sent)

    def _tr_suffix_scope(self, token: Any) -> tuple[str, ...]:
        """-sız/-siz suffix scope'u (bağlı olduğu isim/fiil)."""
        if token.head and token.head != token:
            return tuple(t.text for t in token.head.subtree)
        return (token.text,)

    # ── English Scope Resolution ──
    def _en_surface_scope(self, token: Any) -> tuple[str, ...]:
        """İngilizce negasyon scope'u (basit: cümlenin geri kalanı)."""
        sent_tokens = list(token.sent)
        try:
            token_idx = sent_tokens.index(token)
            return tuple(t.text for t in sent_tokens[token_idx + 1 :])
        except ValueError:
            return ()

    def _resolve_scopes(
        self, doc: Any, cues: list[NegationCue], lang: LanguageCode
    ) -> list[NegationCue]:
        return cues

    # ── Compound Detection ──
    def _detect_compound_negation(
        self, cues: list[NegationCue], lang: LanguageCode
    ) -> list[NegationCue]:
        """Birden fazla negasyonun birleşimini tespit et."""
        if len(cues) < 2:
            return cues

        if lang == LanguageCode.TR:
            surface_cues = [c for c in cues if c.negation_type == NegationType.SURFACE]
            syntactic_cues = [
                c for c in cues if c.negation_type == NegationType.SYNTACTIC
            ]

            if surface_cues and syntactic_cues:
                strongest = max(cues, key=lambda c: len(c.scope_tokens))
                modified = [c for c in cues if c != strongest]
                modified.append(
                    NegationCue(
                        cue_text=f"COMPOUND:{strongest.cue_text}",
                        cue_start=strongest.cue_start,
                        cue_end=strongest.cue_end,
                        negation_type=NegationType.COMPOUND,
                        sentence_id=strongest.sentence_id,
                        language=lang,
                        scope_tokens=strongest.scope_tokens,
                        confidence=min(1.0, strongest.confidence + 0.1),
                    )
                )
                return modified

        return cues
