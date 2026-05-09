from enum import Enum


class SpeakerRole(str, Enum):
    HEAD_OF_STATE = "head_of_state"
    HEAD_OF_GOVERNMENT = "head_of_government"
    VICE_PRESIDENT = "vice_president"
    MINISTER = "minister"
    DEPUTY_MINISTER = "deputy_minister"
    INTL_OFFICIAL = "intl_official"
    DIPLOMAT = "diplomat"
    ADVISOR = "advisor"
    EXPERT = "expert"
    MODERATOR = "moderator"
    JOURNALIST = "journalist"
    PANELIST = "panelist"

    @property
    def power_level(self) -> int:
        return {
            "head_of_state": 10,
            "head_of_government": 9,
            "vice_president": 8,
            "minister": 7,
            "deputy_minister": 6,
            "intl_official": 7,
            "diplomat": 6,
            "advisor": 5,
            "expert": 4,
            "moderator": 3,
            "journalist": 2,
            "panelist": 3,
        }[self.value]
