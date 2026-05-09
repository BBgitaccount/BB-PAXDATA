from enum import Enum


class AnomalyType(str, Enum):
    RISK_HEDGING_CONFLICT = "risk_hedging_conflict"
    NEGATIVE_CONFRONTATIONAL_AMPLIFICATION = "negative_confrontational_amplification"
    VELVET_GLOVE_CONFRONTATION = "velvet_glove_confrontation"
    HIGH_RISK_CONCILIATORY_MASK = "high_risk_conciliatory_mask"
    DIRECT_MANIPULATION_LOW_HEDGE = "direct_manipulation_low_hedge"
    DOMINANT_ACTOR_PRESSURE = "dominant_actor_pressure"
    VAGUE_DEMAND_PLAUSIBLE_DENIABILITY = "vague_demand_plausible_deniability"
    CONFLICT_FRAME_POSITIVE_WRAP = "conflict_frame_positive_wrap"
    INCONSISTENCY_PLUS_MANIPULATION = "inconsistency_plus_manipulation"
    NEGATIVE_APPRAISAL_PERSUASIVE_TONE = "negative_appraisal_persuasive_tone"
