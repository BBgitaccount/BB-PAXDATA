from enum import Enum


class RiskTrajectory(str, Enum):
    ESCALATING = "escalating"
    DE_ESCALATING = "de-escalating"
    STABLE = "stable"
