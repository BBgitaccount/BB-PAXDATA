from __future__ import annotations

import asyncio
import json

import typer
from bb_paxdata.application.cli.use_cases.validation import (
    Severity,
    ValidationResult,
    ValidationUseCase,
)
from bb_paxdata.config.settings import get_settings
from bb_paxdata.infrastructure.persistence.session import get_session_factory
from bb_paxdata.infrastructure.persistence.validators.data_validator import (
    SQLDataValidator,
)
from bb_paxdata.infrastructure.persistence.validators.schema_validator import (
    AlembicSchemaValidator,
)
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Database consistency, integrity and anomaly check")
console = Console()

_SEVERITY_COLOR = {
    Severity.CRITICAL: "red",
    Severity.WARNING: "yellow",
    Severity.INFO: "blue",
}


def _render_table(result: ValidationResult) -> None:
    status = "[green]✅ PASSED[/green]" if result.passed else "[red]❌ FAILED[/red]"
    table = Table(
        title=f"Validation Report — {status}",
        show_header=True,
        header_style="bold",
        border_style="dim",
    )
    table.add_column("Severity", min_width=10)
    table.add_column("Check", min_width=25)
    table.add_column("Message", min_width=40)
    table.add_column("Row", justify="right", min_width=8)
    table.add_column("Suggestion", min_width=25, style="dim")

    for issue in sorted(result.issues, key=lambda i: i.severity.value):
        c = _SEVERITY_COLOR[issue.severity]
        table.add_row(
            f"[{c}]{issue.severity.value}[/{c}]",
            issue.check_name,
            issue.message,
            str(issue.affected_rows or "—"),
            issue.suggested_fix or "—",
        )

    console.print(table)
    console.print(
        f"\n[dim]Total checks: {result.total_checks} | "
        f"Critical: {result.critical_count} | "
        f"Warning: {result.warning_count} | "
        f"Duration: {result.duration_sec:.3f}s[/dim]"
    )


@app.command(name="db")
def validate_db(
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Treat WARNINGs as errors",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Machine readable JSON output",
    ),
    output_file: str | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write results to JSON file",
    ),
) -> None:
    """Validate database in five dimensions."""
    settings = get_settings()
    session_factory = get_session_factory(settings.database_url)

    use_case = ValidationUseCase(
        schema_checker=AlembicSchemaValidator(
            alembic_ini=str(settings.alembic_ini_path)
        ),
        data_checker=SQLDataValidator(),
        session_factory=session_factory,
    )

    result: ValidationResult = asyncio.run(use_case.execute())

    if json_output or output_file:
        payload = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(payload)
            console.print(f"[green]✓[/green] Report written: {output_file}")
        else:
            typer.echo(payload)
        return

    _render_table(result)

    fails = (not result.passed) or (strict and result.warning_count > 0)
    if fails:
        raise typer.Exit(code=1)


@app.command(name="legacy-compare")
def validate_legacy_compare(
    legacy_db: str = typer.Option(
        ...,
        "--legacy-db",
        "-l",
        help="Legacy DB path",
        envvar="BBPAX_LEGACY_DB_PATH",
    ),
) -> None:
    """
    Source/target row count and hash comparison after migration.
    Should be run immediately after migration for data integrity guarantee.
    """
    console.print("[dim]Legacy comparison starting...[/dim]")
    # Note: This command will be active after Phase 3 & 4
    # It will compare row hashes with LegacySQLiteReader + ModernReader.
    console.print(
        "[yellow]This check will be active when Phase 3+4 is complete.[/yellow]"
    )
