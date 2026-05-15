from __future__ import annotations

import os

import typer
from rich.console import Console

app = typer.Typer(
    name="BB-PAXDATA",
    help="[bold cyan]Diplomatic Discourse Analysis Engine[/bold cyan] — CLI Interface",
    no_args_is_help=True,
    # Shell completion injected automatically by Typer
    add_completion=True,
)

err_console = Console(stderr=True)


def _lazy_import_commands() -> None:
    """
    Lazy import commands to prevent circular imports and slow startup.
    This function runs once during `entrypoint()` call.
    """
    try:
        from bb_paxdata.application.commands import build
        from bb_paxdata.interfaces.cli import completions
        from bb_paxdata.interfaces.cli.commands import (
            migrate,
            validate,
        )

        app.add_typer(
            migrate.app,
            name="migrate",
            help="Migration from legacy format to new format",
        )
        app.add_typer(validate.app, name="validate", help="Database consistency check")
        app.add_typer(
            build.app, name="build", help="Build database from transcript files"
        )
        app.add_typer(
            completions.app, name="completions", help="Shell autocomplete management"
        )
    except ImportError:
        # Commands might not be created yet
        pass


@app.callback(invoke_without_command=True)
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version information and exit",
        is_eager=True,
    ),
    config: str | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Custom .env file path",
        envvar="BBPAX_ENV_FILE",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="Increase log output to DEBUG level",
    ),
) -> None:
    """Global CLI callback. Runs before every subcommand."""
    if version:
        from bb_paxdata.config.settings import get_settings

        s = get_settings()
        typer.echo(f"{s.app_name} v{s.version} (Python 3.12+, SQLAlchemy 2.0 Async)")
        raise typer.Exit()

    if config:
        # Runtime .env file change
        os.environ["BBPAX_ENV_FILE"] = config
        from bb_paxdata.config.settings import reset_settings

        reset_settings()

    if verbose:
        os.environ["BBPAX_LOG_LEVEL"] = "DEBUG"
        from bb_paxdata.config.settings import reset_settings

        reset_settings()


def entrypoint() -> None:
    """
    pyproject.toml entry point'i.
    [tool.poetry.scripts]
    bbpaxdata = "bb_paxdata.interfaces.cli.main:entrypoint"
    """
    _lazy_import_commands()
    app()
