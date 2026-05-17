from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spacy.language import Language

from spacy.tokens import Doc, Token

from bb_paxdata.domain.enums.signal_type import SignalType
from bb_paxdata.domain.models.risk_signal import RiskSignal


class RiskSignalDetector:
    """Diplomatik metindeki risk sinyallerini tespit eden servis.

    Zagare (2004) escalation multipliers + Trager (2010) costly/cheap signal
    ayrımı üzerine kuruludur.
    """

    # Zagare (2004) Red Line Signals — geri dönülmez eşik ifadeleri
    RED_LINE_CUES: frozenset[str] = frozenset(
        {
            "red line",
            "unacceptable",
            "non-negotiable",
            "bottom line",
            "will not tolerate",
            "cannot accept",
            "cross the line",
            "line in the sand",
            "point of no return",
            "last straw",
        }
    )

    # Zagare (2004) Retaliation Signals — doğrudan karşı hamle/tehdit
    RETALIATION_CUES: frozenset[str] = frozenset(
        {
            "retaliation",
            "retaliate",
            "strike back",
            "countermeasure",
            "sanctions",
            "punitive",
            "reprisal",
            "reciprocal action",
            "will respond",
            "will act",
            "reserve the right to",
            "all options are on the table",
            "military option",
            "force",
        }
    )

    # Trager (2010) Costly Signals — yüksek taahhüt maliyeti
    COSTLY_CUES: frozenset[str] = frozenset(
        {
            "we will",
            "we shall",
            "commit to",
            "pledge to",
            "bind ourselves",
            "guarantee",
            "assure",
            "formally commit",
            "treaty-bound",
            "irreversible",
            "irrevocable",
        }
    )

    # Trager (2010) Cheap Talk — düşük maliyetli ifadeler
    CHEAP_TALK_CUES: frozenset[str] = frozenset(
        {
            "we hope",
            "we wish",
            "we would like",
            "preferably",
            "ideally",
            "it would be nice",
            "we trust",
            "confident that",
            "expect",
            "anticipate",
            "believe",
        }
    )

    def __init__(self, nlp: Language) -> None:
        self._nlp = nlp

    async def detect(self, text: str, sentence_id: str) -> Sequence[RiskSignal]:
        """Metindeki tüm risk sinyallerini tespit et.

        Phrase-match öncelikli (multi-word cues), sonra single-word.
        """
        doc: Doc = self._nlp(text)
        signals: list[RiskSignal] = []

        # Phrase-level detection (multi-word cues önce)
        signals.extend(self._detect_phrases(text, sentence_id))

        # Single-word/token detection (phrase ile overlap olmayanlar)
        detected_spans = {(s.signal_start, s.signal_end) for s in signals}

        for token in doc:
            # Check if this token is already part of a detected phrase
            is_overlapped = False
            for start, end in detected_spans:
                if token.idx >= start and token.idx < end:
                    is_overlapped = True
                    break

            if is_overlapped:
                continue

            signal = self._detect_single_token(token, sentence_id)
            if signal:
                signals.append(signal)

        # Sort by position
        return tuple(sorted(signals, key=lambda s: s.signal_start))

    def _detect_phrases(self, text: str, sentence_id: str) -> list[RiskSignal]:
        """Multi-word phrase detection (case-insensitive substring match)."""
        signals: list[RiskSignal] = []
        text_lower = text.lower()

        all_phrases = [
            (self.RED_LINE_CUES, SignalType.RED_LINE, 1.5),
            (self.RETALIATION_CUES, SignalType.RETALIATION, 2.0),
            (self.COSTLY_CUES, SignalType.COSTLY_SIGNAL, 1.0),
            (self.CHEAP_TALK_CUES, SignalType.CHEAP_TALK, 1.0),
        ]

        for cue_set, sig_type, multiplier in all_phrases:
            for cue in cue_set:
                idx = text_lower.find(cue)
                while idx != -1:
                    # Credibility: costly > red_line > retaliation > cheap_talk
                    credibility = {
                        SignalType.COSTLY_SIGNAL: 0.9,
                        SignalType.RED_LINE: 0.75,
                        SignalType.RETALIATION: 0.7,
                        SignalType.CHEAP_TALK: 0.3,
                    }[sig_type]

                    signals.append(
                        RiskSignal(
                            signal_text=text[idx : idx + len(cue)],
                            signal_start=idx,
                            signal_end=idx + len(cue),
                            signal_type=sig_type,
                            escalation_multiplier=multiplier,
                            credibility_score=credibility,
                            sentence_id=sentence_id,
                        )
                    )
                    idx = text_lower.find(cue, idx + 1)

        return signals

    def _detect_single_token(self, token: Token, sentence_id: str) -> RiskSignal | None:
        """Tek token risk sinyali tespiti."""
        lower = token.lower_

        if lower in {"sanctions", "retaliation", "reprisal", "force"}:
            return RiskSignal(
                signal_text=token.text,
                signal_start=token.idx,
                signal_end=token.idx + len(token.text),
                signal_type=SignalType.RETALIATION,
                escalation_multiplier=2.0,
                credibility_score=0.7,
                sentence_id=sentence_id,
            )

        if lower in {"guarantee", "pledge", "commit", "bind"}:
            return RiskSignal(
                signal_text=token.text,
                signal_start=token.idx,
                signal_end=token.idx + len(token.text),
                signal_type=SignalType.COSTLY_SIGNAL,
                escalation_multiplier=1.0,
                credibility_score=0.9,
                sentence_id=sentence_id,
            )

        return None
