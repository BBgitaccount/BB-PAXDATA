from enum import Enum


class SignalType(str, Enum):
    """Trager (2010) sinyal türleri + Zagare (2004) tırmanış seviyeleri."""

    CHEAP_TALK = "cheap_talk"  # Düşük maliyetli, düşük güvenilirlik
    COSTLY_SIGNAL = "costly_signal"  # Yüksek maliyetli, güvenilir
    RED_LINE = "red_line"  # Zagare: geri dönülmez eşik (×1.5)
    RETALIATION = "retaliation"  # Zagare: doğrudan karşı hamle (×2.0)
