import io
import os
import subprocess
import sys
import time

# Fix Windows console encoding for Turkish/Unicode characters (cp1252 → utf-8)
if sys.platform == "win32":
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer, encoding="utf-8", errors="replace"
        )

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Initialize rich console for premium styling
console = Console()

PANELS = [
    "01_ahmed_al-sharaa",
    "02_cevdet_yılmaz",
    "03_erdoğan",
    "04_avrupa_başkanları",
    "05_gazze_konuşması",
    "06_mevlüt_çavuşoğlu_ve_cumhurbaşkanları",
    "07_sergei_lavrov",
    "08_somali",
    "09_tom_barrack",
    "10_ukrayna_dışişleri_bakanı",
    "11_hakan_fidan",
    "12_climate",
]


def run_command(args: list[str], step_name: str) -> tuple[bool, str, float]:
    """Runs a command and returns success status, captured output, and duration."""
    console.print(f"\n[bold blue]>>> Running Step: {step_name}[/bold blue]")
    console.print(f"[dim]Command: {' '.join(args)}[/dim]\n")

    start_time = time.time()
    try:
        # Run process, redirecting stdout/stderr to console but capturing it if needed
        # We allow it to print in real-time for visibility, but we can capture exit code
        result = subprocess.run(args, check=False)
        duration = time.time() - start_time
        success = result.returncode == 0
        return success, f"Exit Code: {result.returncode}", duration
    except Exception as e:
        duration = time.time() - start_time
        return False, str(e), duration


def print_summary_report(report_data: list, total_duration: float) -> None:
    """Renders a beautiful summary table of all pipeline steps."""
    console.print("\n")
    table = Table(
        title="[bold cyan]BB-PAXDATA PIPELINE RUN SUMMARY REPORT[/bold cyan]",
        show_header=True,
        header_style="bold magenta",
        border_style="cyan",
    )
    table.add_column("Pipeline Step", style="white", min_width=30)
    table.add_column("Status", justify="center", min_width=12)
    table.add_column("Duration", justify="right", min_width=12)
    table.add_column("Details", style="dim", min_width=30)

    all_passed = True
    for step, success, dur_str, details in report_data:
        status_str = (
            "[bold green]PASSED[/bold green]"
            if success
            else "[bold red]FAILED[/bold red]"
        )
        if not success:
            all_passed = False
        table.add_row(step, status_str, dur_str, details)

    console.print(table)

    overall_status = (
        "[bold green]ALL STAGES PASSED SUCCESSFULLY![/bold green]"
        if all_passed
        else "[bold red]SOME PIPELINE STAGES FAILED![/bold red]"
    )
    console.print(
        Panel(
            f"  • Overall Status: {overall_status}\n"
            f"  • Total Time:     [bold yellow]{total_duration:.2f} seconds[/bold yellow]",
            border_style="green" if all_passed else "red",
        )
    )

    if not all_passed:
        sys.exit(1)


def main() -> None:
    console.clear()
    console.print(
        Panel.fit(
            "[bold cyan]BB-PAXDATA DIPLOMATIC DISCOURSE ANALYSIS ENGINE[/bold cyan]\n"
            "[bold white]End-to-End Pipeline Execution & Verification[/bold white]",
            border_style="cyan",
        )
    )

    # Try to load app settings to detect AI mode
    is_ai_enabled = False
    database_url = "SQLite (default)"
    database_mode = "sqlite"

    try:
        # Setup path so we can import bb_paxdata config
        sys.path.insert(
            0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src"))
        )
        from bb_paxdata.config.settings import get_settings

        settings = get_settings()

        # Read active configuration
        database_url = settings.database_url or "sqlite+aiosqlite:///paxdata.db"
        database_mode = (
            settings.database_mode.value
            if hasattr(settings.database_mode, "value")
            else str(settings.database_mode)
        )

        # AI Detection
        api_key = settings.active_ai_api_key
        if api_key and api_key != "your_key_here":
            is_ai_enabled = True

        console.print("[green][OK][/green] Successfully loaded settings from config.")
        console.print(
            f"  • Database Mode: [bold yellow]{database_mode.upper()}[/bold yellow]"
        )
        console.print(f"  • Database URL:  [dim]{database_url}[/dim]")
        console.print(
            f"  • AI Provider:  [bold green]{settings.ai_provider.value}[/bold green] (AI Enabled: [bold]{is_ai_enabled}[/bold])"
        )
    except Exception as e:
        console.print(
            f"[yellow][WARN][/yellow] Could not load app settings: {e}. Falling back to default settings."
        )

    # Ingestion build flags
    build_flags = [
        "poetry",
        "run",
        "paxdata",
        "build",
        "build",
        "data/Antalya Diplomatic Forum 2026",
        "--force-rebuild",
    ]
    if not is_ai_enabled:
        console.print(
            "[yellow][INFO] No active AI API key found. Running build in --logic-only mode.[/yellow]"
        )
        build_flags.append("--logic-only")
    else:
        console.print(
            "[green][INFO] Active AI API key detected. Running build with full AI Analysis.[/green]"
        )

    report_data = []
    pipeline_start_time = time.time()

    # Step 1: Install spaCy NLP models
    console.print(
        "\n[bold blue]>>> Running Step: Install spaCy NLP Models[/bold blue]\n"
    )
    spacy_success = True
    spacy_models = {
        "en_core_web_sm": "https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl",
        "tr_core_news_md": "https://huggingface.co/turkish-nlp-suite/tr_core_news_md/resolve/main/tr_core_news_md-1.0-py3-none-any.whl",
    }
    for model, url in spacy_models.items():
        # Check if the model is already installed and loadable in the virtual environment
        console.print(
            f"Checking if spaCy model [bold cyan]{model}[/bold cyan] is installed..."
        )
        check_cmd = [
            "poetry",
            "run",
            "python",
            "-c",
            f"import spacy; spacy.load('{model}')",
        ]
        check_res = subprocess.run(
            check_cmd, capture_output=True, text=True, check=False
        )

        if check_res.returncode == 0:
            console.print(
                f"[green][OK] {model} is already installed and loadable.[/green]"
            )
            report_data.append(
                (f"Check/Install spaCy - {model}", True, "0.00s", "Already installed")
            )
        else:
            console.print(
                f"[yellow]{model} not found or not loadable. Installing...[/yellow]"
            )
            cmd = ["poetry", "run", "pip", "install", url]
            s_success, s_msg, s_dur = run_command(cmd, f"Install spaCy: {model}")
            report_data.append(
                (f"Install spaCy - {model}", s_success, f"{s_dur:.2f}s", s_msg)
            )
            if not s_success:
                console.print(f"[red]Failed to install {model}[/red]")
                spacy_success = False
            else:
                console.print(f"[green]Successfully installed {model}[/green]")

    if not spacy_success:
        console.print(
            "[bold red]Critical Error: Failed to install any spaCy NLP model! Stopping pipeline.[/bold red]"
        )
        print_summary_report(report_data, time.time() - pipeline_start_time)
        sys.exit(1)

    # Step 2: Database migrations
    success, msg, duration = run_command(
        ["poetry", "run", "alembic", "upgrade", "head"], "Database Migration (Alembic)"
    )
    report_data.append(("Database Migrations", success, f"{duration:.2f}s", msg))
    if not success:
        console.print(
            "[bold red]Critical Error: Database migrations failed! Stopping pipeline.[/bold red]"
        )
        print_summary_report(report_data, time.time() - pipeline_start_time)
        sys.exit(1)

    # Step 3: Build database from transcripts
    success, msg, duration = run_command(build_flags, "Database Build & Ingestion")
    report_data.append(("Database Build & Ingestion", success, f"{duration:.2f}s", msg))
    if not success:
        console.print(
            "[bold red]Critical Error: Database build failed! Stopping pipeline.[/bold red]"
        )
        print_summary_report(report_data, time.time() - pipeline_start_time)
        sys.exit(1)

    # Step 4: Run full analysis for all panels
    console.print(
        "\n[bold blue]>>> Running Step: Full Discourse & Topic Analysis on all 12 Panels[/bold blue]\n"
    )
    analysis_success = True
    analysis_start = time.time()

    for panel in PANELS:
        console.print(f"Analyzing panel: [bold cyan]{panel}[/bold cyan]...")
        cmd = ["poetry", "run", "paxdata", "analyze", "full", "--panel-id", panel]
        p_success, p_msg, p_dur = run_command(cmd, f"Analysis: {panel}")
        report_data.append((f"Analysis - {panel}", p_success, f"{p_dur:.2f}s", p_msg))
        if not p_success:
            analysis_success = False

    analysis_duration = time.time() - analysis_start
    if analysis_success:
        console.print(
            f"\n[bold green]All panels analyzed successfully in {analysis_duration:.2f}s[/bold green]"
        )
    else:
        console.print(
            f"\n[bold red]Some panels failed analysis. Time taken: {analysis_duration:.2f}s[/bold red]"
        )

    # Print Final Summary Report
    print_summary_report(report_data, time.time() - pipeline_start_time)


if __name__ == "__main__":
    main()
