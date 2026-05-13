from __future__ import annotations

from pathlib import Path

# Project Root
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()

# Version
VERSION = "6.0.0"

# Default Paths
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "bb-paxdata.db"
DEFAULT_ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"

# AI Recovery
MAX_JSON_RECOVERY_ATTEMPTS = 3
