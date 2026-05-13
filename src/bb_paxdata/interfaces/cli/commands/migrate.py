from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from bb_paxdata.application.cli.use_cases.migration import (
    MigrationResult,
    MigrationUseCase,
)
from bb_paxdata.config.settings import get_settings, override_settings
from bb_paxdata.infrastructure.persistence.legacy.sqlite_reader import (
    LegacySQLiteReader,
)
from bb_paxdata.infrastructure.persistence.modern.sqlalchemy_writer import (
    ModernSQLAlchemyWriter,
)
from bb_paxdata.infrastructure.persistence.session import get_session_factory
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)
from rich.table import Table

app = typer.Typer(
    help="Migration from legacy monolithic SQLite DB to new modular format"
)
console = Console()


def _build_result_table(result: MigrationResult) -> Table:
    table = Table(
        title=f"Migration Result — {'✅ SUCCESS' if result.status == 'completed' else '⚠ PARTIAL'}",
        show_header=True,
        header_style="bold magenta",
        border_style="dim",
    )
    table.add_column("Metric", style="cyan", min_width=20)
    table.add_column("Value", style="bold")

    table.add_row("Source Rows", str(result.total_source_rows))
    table.add_row("Migrated", f"[green]{result.migrated_rows}[/green]")
    table.add_row(
        "Failed",
        f"[{'red' if result.failed_rows else 'dim'}]{result.failed_rows}[/{'red' if result.failed_rows else 'dim'}]",
    )
    table.add_row("Retry Attempted", str(result.retried_rows))
    table.add_row("Success Rate", f"{result.success_rate}%")
    table.add_row("Duration (sec)", f"{result.duration_sec:.3f}")
    table.add_row("Error Count", str(len(result.errors)))
    return table


@app.command(name="run")
def migrate_run(
    legacy_db: str = typer.Option(
        ...,
        "--legacy-db",
        "-l",
        help="Path to legacy SQLite DB file",
        envvar="BBPAX_LEGACY_DB_PATH",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Simulate without actual writing",
    ),
    batch_size: int | None = typer.Option(
        None,
        "--batch-size",
        "-b",
        help="Batch size (overrides settings.batch_size)",
        min=1,
        max=500,
    ),
    stop_on_error: bool = typer.Option(
        False,
        "--stop-on-error",
        help="Stop after first error (default: continue)",
    ),
) -> None:
    """Start migration. Partial success returns exit code 2."""
    legacy_path = Path(legacy_db).expanduser().resolve()

    if not legacy_path.exists():
        console.print(
            Panel(
                f"[red]File not found:[/red] {legacy_path}",
                title="Error",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)

    settings = get_settings()
    if batch_size:
        settings = override_settings(batch_size=batch_size)

    if dry_run:
        console.print(
            Panel(
                "[yellow]DRY-RUN mode: No data will be written.[/yellow]",
                border_style="yellow",
            )
        )

    reader = LegacySQLiteReader(str(legacy_path))
    writer = ModernSQLAlchemyWriter(dry_run=dry_run)
    session_factory = get_session_factory(settings.database_url)

    use_case = MigrationUseCase(
        settings=settings,
        legacy_reader=reader,
        modern_writer=writer,
        session_factory=session_factory,
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("Migration running...", total=None)
        result: MigrationResult = asyncio.run(use_case.execute(dry_run=dry_run))

    console.print(_build_result_table(result))

    if result.errors:
        console.print("\n[yellow]First 5 Errors:[/yellow]")
        for err in result.errors[:5]:
            console.print(f"  [dim]•[/dim] {err}")
        if len(result.errors) > 5:
            console.print(f"  [dim]...and {len(result.errors) - 5} more errors[/dim]")

    if result.failed_rows > 0:
        raise typer.Exit(code=2)
    if result.status == "partial":
        raise typer.Exit(code=2)
