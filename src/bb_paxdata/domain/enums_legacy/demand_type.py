from enum import Enum


class DemandType(str, Enum):
    OBLIGATORY = "obligatory"
    CALL_TO_ACTION = "call_to_action"
    RECOMMENDATION = "recommendation"
    INTENTION = "intention"
    EXPECTATION = "expectation"
