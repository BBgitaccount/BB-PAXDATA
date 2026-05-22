# src/bb_paxdata/infrastructure/nlp/readability.py
from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict  # pyright: ignore[reportMissingImports]

# Pre-compiled regex patterns for English syllable count rules to optimize performance
_LE_ENDING_RE = re.compile(r"[^aeiouy]le$")
_SIBILANT_ES_RE = re.compile(r"[szxchsh]es$")
_CG_ES_RE = re.compile(r"[cg]es$")
_LE_ES_RE = re.compile(r"[^aeiouy]les$")
_TD_ED_RE = re.compile(r"[td]ed$")
_LE_ED_RE = re.compile(r"[^aeiouy]led$")
_SENTENCE_SPLIT_RE = re.compile(r"[.!?]+")
_WORD_EXTRACT_RE = re.compile(r"\b\w+\b")


class ReadabilityScores(BaseModel):
    model_config = ConfigDict(frozen=True)

    gunning_fog: float
    flesch_reading_ease: float
    flesch_kincaid_grade: float
    constructive_ambiguity_flag: bool
    abstract_words_ratio: float
    word_count: int
    sentence_count: int


def count_syllables(word: str, language: str = "en") -> int:
    """Deterministic syllable counter supporting English and Turkish."""
    word = word.lower().strip(".,;:!?\"'()[]-")
    if not word:
        return 0

    if language == "tr":
        # Turkish vowels: one syllable per vowel
        tr_vowels = "aeıioöuü"
        return sum(1 for char in word if char in tr_vowels)
    else:
        # English syllables approximation
        vowels = "aeiouy"
        count = 0
        in_vowel_seq = False
        for char in word:
            if char in vowels:
                if not in_vowel_seq:
                    count += 1
                    in_vowel_seq = True
            else:
                in_vowel_seq = False

        # End rules
        if word.endswith("e") and count > 1:
            if not _LE_ENDING_RE.search(word):
                count -= 1
        elif word.endswith("es") and count > 1:
            if not (
                _SIBILANT_ES_RE.search(word)
                or _CG_ES_RE.search(word)
                or _LE_ES_RE.search(word)
            ):
                count -= 1
        elif word.endswith("ed") and count > 1:
            if not (_TD_ED_RE.search(word) or _LE_ED_RE.search(word)):
                count -= 1

        return max(1, count)


def is_abstract_word(word: str, language: str = "en") -> bool:
    """Determine if a word is an abstraction cue using suffixes and lookup."""
    word = word.lower().strip(".,;:!?\"'()[]-")
    if not word:
        return False

    abstract_list_en = {
        "democracy",
        "sovereignty",
        "stability",
        "security",
        "solidarity",
        "prosperity",
        "justice",
        "cooperation",
        "flexibility",
        "autonomy",
        "freedom",
        "peace",
        "conflict",
        "alliance",
        "negotiation",
        "dialogue",
        "responsibility",
    }

    abstract_list_tr = {
        "demokrasi",
        "egemenlik",
        "istikrar",
        "güvenlik",
        "dayanışma",
        "refah",
        "adalet",
        "işbirliği",
        "esneklik",
        "özerklik",
        "özgürlük",
        "barış",
        "çatışma",
        "ittifak",
        "müzakere",
        "diyalog",
        "sorumluluk",
    }

    if language == "tr":
        if word in abstract_list_tr:
            return True
        # Turkish suffixes for abstraction: -lik, -cilik, -izm, -iyet, -sel, -sal
        if word.endswith(
            (
                "lik",
                "lık",
                "lük",
                "luk",
                "cilik",
                "cılık",
                "cülük",
                "culuk",
                "izm",
                "iyet",
                "sel",
                "sal",
            )
        ):
            return True
    else:
        if word in abstract_list_en:
            return True
        # English suffixes for abstraction: -ity, -ism, -tion, -ness, -ment, -ance, -ece
        if word.endswith(("ity", "ism", "tion", "ness", "ment", "ance", "ence")):
            return True

    return False


class ReadabilityAnalyzer:
    """Analyzes text readability and strategic obfuscation."""

    def __init__(self, language: str = "en") -> None:
        self.language = language

    def analyze(self, text: str) -> ReadabilityScores:
        if not text.strip():
            return ReadabilityScores(
                gunning_fog=0.0,
                flesch_reading_ease=0.0,
                flesch_kincaid_grade=0.0,
                constructive_ambiguity_flag=False,
                abstract_words_ratio=0.0,
                word_count=0,
                sentence_count=0,
            )

        # Simple sentence splitter: . ! ?
        sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
        sentence_count = max(1, len(sentences))

        # Words extraction
        words = [w for w in re.findall(r"\b\w+\b", text) if w]
        word_count = len(words)

        if word_count == 0:
            return ReadabilityScores(
                gunning_fog=0.0,
                flesch_reading_ease=0.0,
                flesch_kincaid_grade=0.0,
                constructive_ambiguity_flag=False,
                abstract_words_ratio=0.0,
                word_count=0,
                sentence_count=0,
            )

        # Syllable and complex word counts
        total_syllables = 0
        complex_word_count = 0
        abstract_word_count = 0

        for word in words:
            syllables = count_syllables(word, self.language)
            total_syllables += syllables
            if syllables >= 3:
                complex_word_count += 1
            if is_abstract_word(word, self.language):
                abstract_word_count += 1

        avg_sentence_len = word_count / sentence_count
        percent_complex = (complex_word_count / word_count) * 100
        avg_syllables_per_word = total_syllables / word_count

        # Readability indices
        gunning_fog = 0.4 * (avg_sentence_len + percent_complex)
        flesch_reading_ease = (
            206.835 - 1.015 * avg_sentence_len - 84.6 * avg_syllables_per_word
        )
        flesch_kincaid_grade = (
            0.39 * avg_sentence_len + 11.8 * avg_syllables_per_word - 15.59
        )

        # Bound scores
        gunning_fog = round(max(0.0, gunning_fog), 4)
        flesch_reading_ease = round(flesch_reading_ease, 4)
        flesch_kincaid_grade = round(flesch_kincaid_grade, 4)

        abstract_ratio = abstract_word_count / word_count

        # Constructive Ambiguity Flag
        # Triggers if the language is academically complex (Gunning Fog > 12)
        # and has a high percentage of abstract words (abstract_ratio > 0.05)
        ambiguity_flag = gunning_fog > 12.0 and abstract_ratio > 0.05

        return ReadabilityScores(
            gunning_fog=gunning_fog,
            flesch_reading_ease=flesch_reading_ease,
            flesch_kincaid_grade=flesch_kincaid_grade,
            constructive_ambiguity_flag=ambiguity_flag,
            abstract_words_ratio=round(abstract_ratio, 4),
            word_count=word_count,
            sentence_count=sentence_count,
        )
