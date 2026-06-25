from enum import StrEnum


class RiskTrajectory(StrEnum):
    ESCALATING = "escalating"
    DE_ESCALATING = "de-escalating"
    STABLE = "stable"
