from __future__ import annotations

import os
import subprocess
from pathlib import Path

import typer
from rich.console import Console

console = Console()

SUPPORTED_SHELLS = ("bash", "zsh", "fish")
MARKER_TMPL = "# ──── BEGIN BB-PAXDATA {shell} completion ────"
END_MARKER_TMPL = "# ──── END BB-PAXDATA {shell} completion ────"

app = typer.Typer(help="Shell autocomplete installation and management")


def _shell_rc_path(shell: str) -> Path:
    """Returns the path to the shell configuration file."""
    home = Path.home()
    mapping = {
        "bash": home / ".bashrc",
        "zsh": home / ".zshrc",
        "fish": home / ".config" / "fish" / "config.fish",
    }
    return mapping[shell]


def _completion_script(shell: str) -> str:
    """
    Generates script using Typer/Click's natural completion mechanism.
    `_BB_PAXDATA_COMPLETE` env variable is Click's source protocol.
    """
    env = {"_BB_PAXDATA_COMPLETE": f"source_{shell}"}
    result = subprocess.run(
        ["bbpaxdata"],
        env={**os.environ, **env},
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Completion script could not be generated.\n" f"stderr: {result.stderr}"
        )
    return result.stdout


@app.command(name="install")
def install_completion(
    shell: str = typer.Argument(
        ..., help=f"Shell type: {' | '.join(SUPPORTED_SHELLS)}"
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing installation",
    ),
) -> None:
    """
    Adds shell completion script to RC file.
    Idempotent: safe to run the same command twice.
    """
    if shell not in SUPPORTED_SHELLS:
        console.print(
            f"[red]Error:[/red] Unsupported shell: '{shell}'. "
            f"Supported: {', '.join(SUPPORTED_SHELLS)}"
        )
        raise typer.Exit(code=1)

    rc_path = _shell_rc_path(shell)
    marker = MARKER_TMPL.format(shell=shell)

    if rc_path.exists():
        content = rc_path.read_text(encoding="utf-8")
        if marker in content:
            if not force:
                console.print(
                    f"[yellow]Warning:[/yellow] Completion already installed: {rc_path}\n"
                    f"Use [bold]--force[/bold] to overwrite."
                )
                raise typer.Exit()
            # Force: clean existing block
            end_marker = END_MARKER_TMPL.format(shell=shell)
            start_idx = content.find(marker)
            end_idx = content.find(end_marker) + len(end_marker)
            content = content[:start_idx] + content[end_idx:]
            rc_path.write_text(content.strip() + "\n", encoding="utf-8")

    try:
        script = _completion_script(shell)
    except Exception as exc:
        console.print(f"[red]Script generation error:[/red] {exc}")
        raise typer.Exit(code=1)

    with rc_path.open("a", encoding="utf-8") as f:
        f.write(f"\n{MARKER_TMPL.format(shell=shell)}\n")
        f.write(script)
        f.write(f"\n{END_MARKER_TMPL.format(shell=shell)}\n")

    console.print(
        f"[green]✓[/green] [bold]{shell}[/bold] completion installed: [dim]{rc_path}[/dim]\n"
        f"[dim]To take effect:[/dim] [bold]source {rc_path}[/bold]"
    )


@app.command(name="show")
def show_completion(
    shell: str = typer.Argument(..., help="Shell type"),
) -> None:
    """Writes completion script to stdout (for manual installation)."""
    if shell not in SUPPORTED_SHELLS:
        console.print(f"[red]Unsupported shell:[/red] {shell}")
        raise typer.Exit(code=1)
    try:
        typer.echo(_completion_script(shell))
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)


@app.command(name="uninstall")
def uninstall_completion(
    shell: str = typer.Argument(..., help="Shell type"),
) -> None:
    """Removes installed completion script from RC file."""
    rc_path = _shell_rc_path(shell)
    if not rc_path.exists():
        console.print(f"[yellow]RC file not found:[/yellow] {rc_path}")
        raise typer.Exit()

    content = rc_path.read_text(encoding="utf-8")
    marker = MARKER_TMPL.format(shell=shell)
    end_marker = END_MARKER_TMPL.format(shell=shell)

    if marker not in content:
        console.print("[yellow]Installed completion not found.[/yellow]")
        raise typer.Exit()

    start_idx = content.find(marker)
    end_idx = content.find(end_marker) + len(end_marker)
    new_content = content[:start_idx].rstrip() + "\n" + content[end_idx:].lstrip()
    rc_path.write_text(new_content, encoding="utf-8")
    console.print(f"[green]✓[/green] Completion removed: {rc_path}")
