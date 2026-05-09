from enum import Enum


class HedgingType(str, Enum):
    EPISTEMIC_HIGH = "epistemic_high"
    EPISTEMIC_MEDIUM = "epistemic_medium"
    ANTI_HEDGE = "anti_hedge"
    APPROXIMATOR = "approximator"
    SHIELD = "shield"
    ATTRIBUTION = "attribution"
    NONE = "none"
