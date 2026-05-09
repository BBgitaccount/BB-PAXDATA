from enum import Enum


class AudienceType(str, Enum):
    GLOBAL_AUDIENCE = "global_audience"
    REGIONAL_AUDIENCE = "regional_audience"
    DOMESTIC_AUDIENCE = "domestic_audience"
    INSTITUTIONAL_AUDIENCE = "institutional_audience"
    BILATERAL_AUDIENCE = "bilateral_audience"
    GENERAL = "general"
