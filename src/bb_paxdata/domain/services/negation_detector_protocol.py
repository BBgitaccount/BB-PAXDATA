from collections.abc import Sequence
from typing import Any, Protocol

from bb_paxdata.domain.models.negation_cue import NegationCue


class NegationDetectorProtocol(Protocol):
    """Domain katmanı negasyon detection servis arayüzü."""

    async def detect(self, text: str, sentence_id: str) -> Sequence[NegationCue]:
        """Verilen metindeki tüm negasyon cue'larını tespit et.

        Args:
            text: Analiz edilecek cümle metni.
            sentence_id: Cümle UUID (NegationCue.sentence_id için).

        Returns:
            Sıralı NegationCue sequence'i (cue_start'a göre artan).
        """
        ...

    async def detect_scope(self, cue: NegationCue, doc: Any) -> NegationCue:
        """spaCy Doc objesi üzerinde cue'nun scope ve focus'unu belirle.

        Args:
            cue: Scope'u belirlenecek cue (scope_token_indices henüz boş olabilir).
            doc: spaCy Doc objesi (infrastructure katmanında import edilir).

        Returns:
            Scope ve focus bilgisi güncellenmiş NegationCue.
        """
        ...
