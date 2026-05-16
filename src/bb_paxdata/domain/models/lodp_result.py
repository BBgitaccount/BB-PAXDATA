from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LODPResult:
    """Monroe (2009) LODP ayırt edici kelime sonucu.

    Attributes:
        word: Ayırt edici kelime.
        z_score: LODP z-skoru (pozitif = corpus1'e özgü, negatif = corpus2'ye özgü).
        log_odds_diff: Log odds farkı.
        corpus1_count: Kelimenin corpus1'deki frekansı.
        corpus2_count: Kelimenin corpus2'deki frekansı.
        se: Standart hata.

    Reference:
        - Monroe, B.L. et al. (2009). Fightin' Words.
    """

    word: str
    z_score: float
    log_odds_diff: float
    corpus1_count: int
    corpus2_count: int
    se: float
