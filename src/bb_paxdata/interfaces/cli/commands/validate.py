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
    Source/target row count and basic sanity comparison after migration.
    """
    import os
    import sqlite3

    console.print(f"[bold]Legacy DB Path:[/bold] {legacy_db}")
    if not os.path.exists(legacy_db):
        console.print("[red]Error: Legacy database file does not exist![/red]")
        raise typer.Exit(code=1)

    settings = get_settings()
    new_db = str(settings.database_path)
    console.print(f"[bold]New DB Path:[/bold] {new_db}")
    if not os.path.exists(new_db):
        console.print("[red]Error: New database file does not exist![/red]")
        raise typer.Exit(code=1)

    conn_old = sqlite3.connect(legacy_db)
    conn_new = sqlite3.connect(new_db)

    try:
        cur_old = conn_old.cursor()
        cur_new = conn_new.cursor()

        # Get tables
        cur_old.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables_old = {row[0] for row in cur_old.fetchall()}

        cur_new.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables_new = {row[0] for row in cur_new.fetchall()}

        table_mappings = {
            "panels": "panels",
            "speakers": "speaker_profiles",
            "segments": "segments",
            "sentences": "sentences",
            "words": "words",
            "demand_records": "demand_records",
            "pattern_records": "pattern_records",
            "panel_dynamics": "panel_dynamics",
            "discourse_network_edges": "discourse_flows",  # new schema stores country-to-country edges in discourse_flows
            "country_references": "country_references",
        }

        table = Table(title="Legacy vs Modern Row Count Comparison")
        table.add_column("Table (Legacy)", style="cyan")
        table.add_column("Legacy Count", justify="right")
        table.add_column("Table (New)", style="green")
        table.add_column("New Count", justify="right")
        table.add_column("Discrepancy", justify="right")

        has_discrepancies = False

        for t_old, t_new in table_mappings.items():
            cnt_old = 0
            cnt_new = 0

            if t_old in tables_old:
                cur_old.execute(f"SELECT COUNT(*) FROM `{t_old}`;")
                cnt_old = cur_old.fetchone()[0]
            else:
                t_old = f"{t_old} [MISSING]"

            if t_new in tables_new:
                cur_new.execute(f"SELECT COUNT(*) FROM `{t_new}`;")
                cnt_new = cur_new.fetchone()[0]
            else:
                t_new = f"{t_new} [MISSING]"

            diff = cnt_new - cnt_old
            diff_str = f"[red]{diff:+}[/red]" if diff != 0 else "[green]0[/green]"
            if diff != 0:
                has_discrepancies = True

            table.add_row(t_old, str(cnt_old), t_new, str(cnt_new), diff_str)

        console.print(table)

        if has_discrepancies:
            console.print(
                "[yellow]⚠ Note: Row count differences are present. This is normal if segments were split differently or extra sentences were processed.[/yellow]"
            )
        else:
            console.print("[green]✓ Row counts are fully matched![/green]")

    except Exception as e:
        console.print(f"[red]Error during comparison: {e}[/red]")
        raise typer.Exit(code=1)
    finally:
        conn_old.close()
        conn_new.close()
