from __future__ import annotations

from enum import StrEnum


class FrameType(StrEnum):
    """Diplomatik metinlerdeki çerçeveleme (framing) türleri.

    Entman (1993)'ın 4 işlevsel çerçevesi ile Iyengar (1991)'ın
    episodic/thematic boyutunu birleştirir. Bir `dominant_frame`
    hem Entman fonksiyonu hem de Iyengar boyutu taşıyabilir.

    References:
        - Entman, R.M. (1993). Framing: Toward Clarification of a
          Fractured Paradigm. Journal of Communication, 43(4), 51–58.
        - Iyengar, S. (1991). Is Anyone Responsible? How Television
          Frames Political Issues.
        - Chong, D. & Druckman, J.N. (2007). Framing Theory.
          Annual Review of Political Science.
    """

    # === Entman (1993) Fonksiyonel Çerçeveler ===
    PROBLEM_DEFINITION = "problem_definition"
    """Sorunun tanımlandığı çerçeve: 'kriz', 'tehdit', 'ihmal'."""

    CAUSE_INTERPRETATION = "cause_interpretation"
    """Nedensellik atfeden çerçeve: 'terör örgütü', 'ekonomik politika'."""

    MORAL_EVALUATION = "moral_evaluation"
    """Ahlaki yargı içeren çerçeve: 'haksız', 'adil', 'meşru'."""

    REMEDY_SUGGESTION = "remedy_suggestion"
    """Çözüm öneren çerçeve: 'müzakere', 'yaptırım', 'işbirliği'."""

    # === Iyengar (1991) Boyutsal Çerçeveler ===
    EPISODIC = "episodic"
    """Tek olay odaklı, somut, anlık çerçeve.

    Örnek: 'Dünkü sınır çatışması...' — bireysel olay, somut aktör.
    """

    THEMATIC = "thematic"
    """Genel bağlam odaklı, yapısal, sistemik çerçeve.

    Örnek: 'Bölgesel güvenlik mimarisi...' — yapısal ilişki, uzun dönem.
    """

    # === Mevcut/Spesifik Çerçeveler (Legacy/Context-Specific) ===
    CONFLICT_FRAME = "conflict_frame"
    SECURITY_FRAME = "security_frame"
    HUMANITARIAN_FRAME = "humanitarian_frame"
    LEGAL_FRAME = "legal_frame"
    NEGOTIATION_FRAME = "negotiation_frame"
    OCCUPATION_FRAME = "occupation_frame"
    TWO_STATE_FRAME = "two_state_frame"
    EFFECTIVENESS_FRAME = "effectiveness_frame"
    SOVEREIGNTY_FRAME = "sovereignty_frame"
    MULTILATERAL_FRAME = "multilateral_frame"
    THREAT_FRAME = "threat_frame"
    DETERRENCE_FRAME = "deterrence_frame"
    PEACE_FRAME = "peace_frame"
    NEUTRAL = "neutral"

    @property
    def is_entman_function(self) -> bool:
        """Bu değer Entman'ın 4 fonksiyonel çerçevesinden biri mi?"""
        return self in {
            FrameType.PROBLEM_DEFINITION,
            FrameType.CAUSE_INTERPRETATION,
            FrameType.MORAL_EVALUATION,
            FrameType.REMEDY_SUGGESTION,
        }

    @property
    def is_iyengar_dimension(self) -> bool:
        """Bu değer Iyengar'ın episodic/thematic boyutundan biri mi?"""
        return self in {FrameType.EPISODIC, FrameType.THEMATIC}

    @property
    def entman_function(self) -> FrameType | None:
        """Eğer bu bir Iyengar boyutu ise, ilişkili Entman fonksiyonu.

        Not: Faz 6'da LLM + embedding hibrit frame detection ile
        `EPISODIC` -> `PROBLEM_DEFINITION` gibi eşleştirmeler otomatik
        çıkarılacaktır. Faz 0'da bu property `None` döner.
        """
        # Faz 6'da implemente edilecek — şu an placeholder
        return None
