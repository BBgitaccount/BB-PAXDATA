from __future__ import annotations

from bb_paxdata.application.domain.enums.severity_level import SeverityLevel

# Type alias: Priority has the exact same LOW/MEDIUM/HIGH/CRITICAL lowercase
# schema as SeverityLevel. No DB migration required.
# Used in: HumanReviewRequest.priority, HumanReviewService.get_pending_reviews().
Priority = SeverityLevel
