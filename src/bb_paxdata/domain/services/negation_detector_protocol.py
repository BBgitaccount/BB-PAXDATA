from typing import Any, Protocol

from bb_paxdata.domain.models.negation_cue import NegationResult


class NegationDetectorProtocol(Protocol):
    """Domain katmanı negasyon detection servis arayüzü."""

    async def detect(
        self, text: str, sentence_id: str, language: str | None = None
    ) -> NegationResult:
        """Verilen metindeki tüm negasyon cue'larını tespit et.

        Args:
            text: Analiz edilecek cümle metni.
            sentence_id: Cümle UUID (NegationCue.sentence_id için).
            language: Dil ipucu (isteğe bağlı).

        Returns:
            NegationResult nesnesi.
        """
        ...

    async def detect_with_doc(
        self, doc: Any, sentence_id: str, language: Any
    ) -> NegationResult:
        """spaCy Doc objesi üzerinde cue'nun scope ve focus'unu belirle.

        Args:
            doc: spaCy Doc objesi.
            sentence_id: Cümle UUID.
            language: Dil.

        Returns:
            NegationResult nesnesi.
        """
        ...
