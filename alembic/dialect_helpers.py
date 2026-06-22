"""Dialect-specific helpers for Alembic migrations.

This module provides utility functions to handle differences between
SQLite and PostgreSQL in database migrations.

Usage in migrations:
    from alembic.dialect_helpers import get_bind, is_postgresql, is_sqlite

    bind = get_bind()
    if is_postgresql(bind):
        # PostgreSQL-specific code
        op.execute("CREATE TYPE my_type AS ENUM (...)")
    else:
        # SQLite-specific code
        pass
"""

from typing import Any

from sqlalchemy import text

from alembic import op


def get_bind() -> Any:
    """Get the current database connection bind."""
    return op.get_bind()


def is_postgresql(bind: Any | None = None) -> bool:
    """Check if the current dialect is PostgreSQL."""
    if bind is None:
        bind = get_bind()
    return bind.dialect.name == "postgresql"


def is_sqlite(bind: Any | None = None) -> bool:
    """Check if the current dialect is SQLite."""
    if bind is None:
        bind = get_bind()
    return bind.dialect.name == "sqlite"


def get_timestamp_default(bind: Any | None = None) -> str:
    """Get the dialect-specific timestamp default value."""
    if is_sqlite(bind):
        return "datetime('now')"
    return "CURRENT_TIMESTAMP"


def get_boolean_default(bind: Any | None = None) -> str:
    """Get the dialect-specific boolean default value."""
    if is_postgresql(bind):
        return "true"
    return "1"


def get_insert_ignore_syntax(
    table_name: str,
    columns: list[str],
    bind: Any | None = None,
) -> str:
    """Get dialect-specific INSERT IGNORE / ON CONFLICT syntax.

    Args:
        table_name: Name of the table
        columns: List of column names
        bind: Optional database bind

    Returns:
        SQL string with appropriate syntax for the dialect
    """
    col_list = ", ".join(columns)
    if is_postgresql(bind):
        return f"INSERT INTO {table_name} ({col_list}) SELECT {col_list} FROM temp_table ON CONFLICT DO NOTHING"
    return f"INSERT OR IGNORE INTO {table_name} ({col_list}) SELECT {col_list} FROM temp_table"


def drop_index(table_name: str, index_name: str, bind: Any | None = None) -> None:
    """Drop an index with dialect-specific syntax.

    PostgreSQL requires schema-qualified index names (table.index),
    while SQLite uses just the index name.

    Args:
        table_name: Name of the table
        index_name: Name of the index
        bind: Optional database bind
    """
    if is_postgresql(bind):
        op.execute(text(f"DROP INDEX IF EXISTS {table_name}.{index_name}"))
    else:
        op.execute(text(f"DROP INDEX IF EXISTS {index_name}"))


def get_constraint_name(
    table_name: str,
    column_name: str,
    constraint_type: str = "fkey",
    bind: Any | None = None,
) -> str:
    """Get dialect-specific constraint naming convention.

    PostgreSQL: {table}_{column}_{type}
    SQLite: {type}_{table}_{column}_{referred_table}

    Args:
        table_name: Name of the table
        column_name: Name of the column
        constraint_type: Type of constraint (fkey, uq, etc.)
        bind: Optional database bind

    Returns:
        Constraint name following dialect convention
    """
    if is_postgresql(bind):
        return f"{table_name}_{column_name}_{constraint_type}"
    return f"{constraint_type}_{table_name}_{column_name}"


def enable_sqlite_legacy_alter(bind: Any | None = None) -> None:
    """Enable SQLite legacy alter table mode for batch operations."""
    if is_sqlite(bind):
        op.execute(text("PRAGMA legacy_alter_table = ON"))


def disable_sqlite_legacy_alter(bind: Any | None = None) -> None:
    """Disable SQLite legacy alter table mode."""
    if is_sqlite(bind):
        op.execute(text("PRAGMA legacy_alter_table = OFF"))


def enable_sqlite_foreign_keys(bind: Any | None = None) -> None:
    """Enable SQLite foreign key constraints."""
    if is_sqlite(bind):
        op.execute(text("PRAGMA foreign_keys = ON"))


def disable_sqlite_foreign_keys(bind: Any | None = None) -> None:
    """Disable SQLite foreign key constraints."""
    if is_sqlite(bind):
        op.execute(text("PRAGMA foreign_keys = OFF"))


def create_postgres_enum(
    type_name: str,
    values: list[str],
    bind: Any | None = None,
) -> None:
    """Create a PostgreSQL ENUM type if it doesn't exist.

    Args:
        type_name: Name of the ENUM type
        values: List of enum values
        bind: Optional database bind
    """
    if not is_postgresql(bind):
        return

    conn = get_bind() if bind is None else bind
    type_exists = conn.scalar(
        text(f"SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = '{type_name}')")
    )
    if not type_exists:
        values_str = ", ".join(f"'{v}'" for v in values)
        op.execute(text(f"CREATE TYPE {type_name} AS ENUM ({values_str})"))


def create_postgres_extension(extension_name: str, bind: Any | None = None) -> None:
    """Create a PostgreSQL extension if it doesn't exist.

    Args:
        extension_name: Name of the extension (e.g., 'vector')
        bind: Optional database bind
    """
    if is_postgresql(bind):
        op.execute(text(f"CREATE EXTENSION IF NOT EXISTS {extension_name}"))
