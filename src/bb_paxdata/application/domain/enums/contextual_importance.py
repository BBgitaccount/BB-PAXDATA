from __future__ import annotations

from bb_paxdata.application.domain.enums.severity_level import SeverityLevel

# Type alias: ContextualImportance has the exact same LOW/MEDIUM/HIGH/CRITICAL
# lowercase schema as SeverityLevel. No DB migration required.
# Used in: Segment domain model (segment.py).
ContextualImportance = SeverityLevel
