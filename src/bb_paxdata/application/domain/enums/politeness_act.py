from enum import StrEnum


class PolitenessAct(StrEnum):
    DIRECT_CRITICISM = "direct_criticism"
    DIRECT_DEMAND = "direct_demand"
    BLAME = "blame"
    HEDGING = "hedging"
    COMPLIMENT = "compliment"
    INDIRECT_REQUEST = "indirect_request"
