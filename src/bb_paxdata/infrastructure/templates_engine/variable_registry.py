# src/bb_paxdata/infrastructure/templates_engine/variable_registry.py
from __future__ import annotations

"""Variable registry for template engine - defines available variables for templates."""

VARIABLE_REGISTRY = {
    # Session variables
    "session.title": {"type": "str", "example": "G20 İklim Zirvesi 2024"},
    "session.date": {"type": "date", "example": "2024-11-15"},
    "session.duration_minutes": {"type": "int", "example": 180},
    "session.location": {"type": "str", "example": "Cenevre"},
    "session.classification": {"type": "str", "example": "CONFIDENTIAL"},
    "session.participant_count": {"type": "int", "example": 12},
    # Speaker variables (list - for loops)
    "speakers": {"type": "list[Speaker]", "example": "[...]"},
    "speaker.name": {"type": "str", "example": "Ahmet Yılmaz"},
    "speaker.country": {"type": "str", "example": "Türkiye"},
    "speaker.statement_count": {"type": "int", "example": 34},
    "speaker.avg_risk_score": {"type": "float", "example": 6.2},
    "speaker.dominant_sbi": {"type": "str", "example": "B"},
    # Analysis variables
    "analysis.summary": {"type": "str", "example": "Bu oturumda..."},
    "analysis.sbi": {"type": "dict", "example": {"S": 45, "B": 30, "I": 25}},
    "analysis.top_themes": {"type": "list[str]", "example": ["iklim", "ekonomi"]},
    "analysis.risk_distribution": {
        "type": "dict",
        "example": {"LOW": 20, "MEDIUM": 15, "HIGH": 5},
    },
    "analysis.key_quotes": {"type": "list[dict]", "example": "[...]"},
    # Risk variables
    "risks": {"type": "list[Risk]"},
    "risk.level": {"type": "str", "example": "HIGH"},
    "risk.description": {"type": "str"},
    "risk.speaker": {"type": "str"},
    "risk.timestamp": {"type": "datetime"},
    # Meta
    "report.generated_at": {"type": "datetime", "example": "2024-11-15T14:30:00Z"},
    "report.generated_by": {"type": "str", "example": "analyst@example.com"},
    "report.version": {"type": "str", "example": "1.0"},
}


def get_variable_info(var_name: str) -> dict | None:
    """Get variable information from registry."""
    return VARIABLE_REGISTRY.get(var_name)


def list_all_variables() -> dict:
    """List all available variables."""
    return VARIABLE_REGISTRY


def validate_variables_used(variables: list[str]) -> list[str]:
    """Validate that used variables exist in registry."""
    unknown = []
    for var in variables:
        if var not in VARIABLE_REGISTRY:
            unknown.append(var)
    return unknown
