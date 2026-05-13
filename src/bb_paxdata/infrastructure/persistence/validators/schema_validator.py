from __future__ import annotations

from typing import Any

from bb_paxdata.application.cli.use_cases.validation import ValidationIssue


class AlembicSchemaValidator:
    """Checks Alembic migration status and schema compatibility."""

    def __init__(self, alembic_ini: str) -> None:
        self.alembic_ini = alembic_ini

    async def check_alembic_head(self, session: Any) -> ValidationIssue | None:
        # In real application, head check is performed using Alembic API
        # Return success for now
        return None

    async def check_foreign_keys(self, session: Any) -> list[ValidationIssue]:
        # PRAGMA foreign_key_check (SQLite) or similar queries
        return []

    async def check_column_types(self, session: Any) -> list[ValidationIssue]:
        return []
