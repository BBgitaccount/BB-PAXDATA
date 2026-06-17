# src/bb_paxdata/domain/services/linguistic_helpers.py


def get_vad_vector(
    diplo_compound: float, emotion_category: str | None
) -> dict[str, float]:
    """Calculates Valence, Arousal, Dominance (VAD) vector from diplomatic sentiment and emotion."""
    # Valence: mapped from diplo_compound [-1, 1] to [0.2, 0.8] approximately
    v = 0.5 + 0.2 * diplo_compound
    v = max(0.0, min(1.0, v))

    # Arousal & Dominance defaults
    a = 0.5
    d = 0.5

    emo = (emotion_category or "").lower()
    if emo in ("confrontational", "concerned", "anger", "fear", "threat", "sadness"):
        a = 0.6
        d = 0.6
    elif emo in (
        "constructive",
        "cooperative",
        "cooperation",
        "joy",
        "friendly",
        "neutral",
    ):
        a = 0.5
        d = 0.5
    else:
        a = 0.4
        d = 0.4

    # Minor adjustment to arousal based on diplomatic intensity
    a += 0.1 * abs(diplo_compound)
    a = max(0.0, min(1.0, a))

    return {"V": round(v, 2), "A": round(a, 2), "D": round(d, 2)}


def classify_speech_act(text: str, demand_count: int) -> str:
    """Classifies the speech act of a text snippet."""
    if demand_count > 0:
        return "DIRECTIVE"

    text_lower = text.lower()
    if any(
        q in text_lower
        for q in ("?", "neler", "kim", "nasıl", "neden", "halk", "soruyorum")
    ):
        return "INTERROGATIVE"

    return "ASSERTIVE"


def get_frame_distribution(text: str, dominant_frame: str | None) -> dict[str, float]:
    """Estimates the framing distribution across major dimensions."""
    frames = {"security": 0.0, "economic": 0.0, "legal": 0.0, "humanitarian": 0.0}

    text_lower = text.lower()

    # Keywords-based scoring
    if any(
        w in text_lower
        for w in (
            "security",
            "stability",
            "threat",
            "force",
            "güvenlik",
            "istikrar",
            "tehdit",
            "askeri",
            "savunma",
        )
    ):
        frames["security"] += 0.5

    if any(
        w in text_lower
        for w in (
            "economic",
            "trade",
            "finance",
            "development",
            "ekonomi",
            "ticaret",
            "finans",
            "kalkınma",
            "büyüme",
        )
    ):
        frames["economic"] += 0.5

    if any(
        w in text_lower
        for w in (
            "legal",
            "law",
            "court",
            "accord",
            "treaty",
            "hukuk",
            "yasa",
            "mahkeme",
            "anlaşma",
            "uluslararası",
        )
    ):
        frames["legal"] += 0.5

    if any(
        w in text_lower
        for w in (
            "humanitarian",
            "rights",
            "refugee",
            "civilian",
            "insani",
            "haklar",
            "mülteci",
            "sivil",
            "yaşam",
        )
    ):
        frames["humanitarian"] += 0.5

    # Apply dominant frame weight if provided
    dom = (dominant_frame or "").lower()
    if dom in frames:
        frames[dom] += 0.5

    # Normalize
    total = sum(frames.values())
    if total > 0:
        for k, value in frames.items():
            frames[k] = round(value / total, 2)
    else:
        # Fallback distribution
        frames["security"] = 0.5
        frames["economic"] = 0.5

    return frames
