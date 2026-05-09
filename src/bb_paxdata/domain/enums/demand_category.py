from enum import Enum


class DemandCategory(str, Enum):
    INSTITUTIONAL_REFORM = "institutional_reform"
    SECURITY_ACTION = "security_action"
    ECONOMIC_COOPERATION = "economic_cooperation"
    HUMANITARIAN_RESPONSE = "humanitarian_response"
    DIPLOMATIC_ENGAGEMENT = "diplomatic_engagement"
    LEGAL_ACCOUNTABILITY = "legal_accountability"
