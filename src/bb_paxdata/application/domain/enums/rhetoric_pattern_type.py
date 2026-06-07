from enum import Enum


class RhetoricPatternType(str, Enum):
    ANAPHORA = "anaphora"
    TRICOLON = "tricolon"
    ANTITHESIS = "antithesis"
    RHETORICAL_Q = "rhetorical_q"
    HISTORICAL_REF = "historical_ref"
    COLLECTIVE_VOICE = "collective_voice"
    URGENCY_MARKER = "urgency_marker"
    EPISTEMIC_HEDGE = "epistemic_hedge"
    MORAL_FRAMING = "moral_framing"
