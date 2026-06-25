from enum import StrEnum


class DemandType(StrEnum):
    OBLIGATORY = "obligatory"
    CALL_TO_ACTION = "call_to_action"
    RECOMMENDATION = "recommendation"
    INTENTION = "intention"
    EXPECTATION = "expectation"
