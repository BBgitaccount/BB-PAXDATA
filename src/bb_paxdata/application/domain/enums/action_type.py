from enum import StrEnum


class ActionType(StrEnum):
    CONDEMN = "CONDEMN"
    SUPPORT = "SUPPORT"
    DEMAND = "DEMAND"
    PROPOSE = "PROPOSE"
    AGREE = "AGREE"
    REJECT = "REJECT"
    THREATEN = "THREATEN"
    OFFER = "OFFER"


def map_frame_to_actions(
    frame: str | None, demand_type: str | None = None
) -> list[ActionType]:
    """Maps a dominant frame and demand type to a list of action types."""
    actions = []

    if demand_type in ("explicit", "implicit"):
        actions.append(ActionType.DEMAND)

    if not frame:
        if not actions:
            actions.append(ActionType.SUPPORT)
        return actions

    frame_clean = frame.lower().strip()

    if frame_clean == "conflict_frame":
        actions.extend([ActionType.CONDEMN, ActionType.THREATEN])
    elif frame_clean in ("negotiation_frame", "multilateral_frame"):
        actions.extend([ActionType.SUPPORT, ActionType.PROPOSE])
    elif frame_clean in (
        "peace_frame",
        "humanitarian_frame",
        "security_frame",
        "sovereignty_frame",
        "effectiveness_frame",
    ):
        actions.append(ActionType.SUPPORT)
    elif frame_clean == "legal_frame":
        actions.append(ActionType.AGREE)
    elif frame_clean in ("threat_frame", "deterrence_frame"):
        actions.append(ActionType.THREATEN)

    if not actions:
        actions.append(ActionType.SUPPORT)  # Fallback default

    # Deduplicate while preserving order
    seen = set()
    result = []
    for a in actions:
        if a not in seen:
            seen.add(a)
            result.append(a)
    return result
