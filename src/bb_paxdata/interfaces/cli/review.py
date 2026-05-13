"""CLI commands for human review queue management."""

import json
import sys
from pathlib import Path
from typing import Any, Literal, cast

import structlog
import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from bb_paxdata.infrastructure.db.human_review_queue import HumanReviewQueue
from bb_paxdata.infrastructure.db.session import get_db_session
from bb_paxdata.quality.review_queue import ReviewQueueManager

logger = structlog.get_logger(__name__)
console = Console()

app = typer.Typer(help="Human review queue management commands")


@app.command("list")
def list_reviews(
    status: str = typer.Option("PENDING", "--status", "-s", help="Filter by status"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum number to show"),
    panel_id: str | None = typer.Option(
        None, "--panel", "-p", help="Filter by panel ID"
    ),
) -> None:
    """List reviews in the queue."""
    try:
        with get_db_session() as session:
            manager = ReviewQueueManager(session)

            if status.upper() == "STATS":
                # Show statistics
                stats = manager.get_queue_statistics()
                _show_statistics(stats)
                return

            # Get reviews
            reviews = manager.get_pending_reviews(limit=limit, panel_id=panel_id)

            if not reviews:
                console.print(f"[yellow]No reviews found with status '{status}'")
                return

            # Display reviews in table
            table = Table(title=f"Review Queue - {status.upper()}")
            table.add_column("ID", style="cyan")
            table.add_column("Sentence ID", style="magenta")
            table.add_column("Panel", style="green")
            table.add_column("Speaker", style="blue")
            table.add_column("Trigger", style="red")
            table.add_column("Risk Score", style="yellow")
            table.add_column("Flagged", style="dim")

            for review in reviews:
                trigger_display = review.trigger_type.replace("_", " ").title()
                risk_display = (
                    str(review.ai_risk_score) if review.ai_risk_score else "N/A"
                )

                table.add_row(
                    str(review.review_id),
                    review.sent_id,
                    review.panel_id or "N/A",
                    review.speaker_name or "N/A",
                    trigger_display,
                    risk_display,
                    review.flagged_at[:19] if review.flagged_at else "N/A",
                )

            console.print(table)

    except Exception as e:
        console.print(f"[red]Error listing reviews: {e}")
        raise typer.Exit(1) from e


@app.command("inspect")
def inspect_review(
    review_id: int = typer.Argument(..., help="Review ID to inspect"),
    show_raw: bool = typer.Option(False, "--raw", "-r", help="Show raw AI output"),
) -> None:
    """Inspect a specific review in detail."""
    try:
        with get_db_session() as session:
            manager = ReviewQueueManager(session)
            review = manager.get_review_by_id(review_id)

            if not review:
                console.print(f"[red]Review {review_id} not found")
                raise typer.Exit(1)

            # Display review details
            _show_review_details(review, show_raw)

    except Exception as e:
        console.print(f"[red]Error inspecting review: {e}")
        raise typer.Exit(1) from e


@app.command("assign")
def assign_review(
    review_id: int = typer.Argument(..., help="Review ID to assign"),
    reviewer: str = typer.Option(..., "--to", "-t", help="Reviewer name"),
) -> None:
    """Assign a review to a person."""
    try:
        with get_db_session() as session:
            manager = ReviewQueueManager(session)

            if manager.assign_review(review_id, reviewer):
                console.print(f"[green]✓ Review {review_id} assigned to {reviewer}")
            else:
                console.print(f"[red]✗ Failed to assign review {review_id}")
                raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]Error assigning review: {e}")
        raise typer.Exit(1) from e


@app.command("start")
def start_review(
    review_id: int = typer.Argument(..., help="Review ID to start"),
) -> None:
    """Mark a review as in progress."""
    try:
        with get_db_session() as session:
            manager = ReviewQueueManager(session)

            if manager.start_review(review_id):
                console.print(f"[green]✓ Review {review_id} marked as in progress")
            else:
                console.print(f"[red]✗ Failed to start review {review_id}")
                raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]Error starting review: {e}")
        raise typer.Exit(1) from e


@app.command("complete")
def complete_review(
    review_id: int = typer.Argument(..., help="Review ID to complete"),
    action: str = typer.Option(
        ..., "--action", "-a", help="Action: APPROVED, REJECTED, MODIFIED"
    ),
    notes: str = typer.Option("", "--notes", "-n", help="Reviewer notes"),
    corrected_file: str = typer.Option(
        None, "--corrected", "-c", help="Path to corrected JSON file"
    ),
) -> None:
    """Complete a review with final action."""
    try:
        # Validate action
        valid_actions = ["APPROVED", "REJECTED", "MODIFIED"]
        if action not in valid_actions:
            console.print(
                f"[red]Invalid action. Must be one of: {', '.join(valid_actions)}"
            )
            raise typer.Exit(1)

        # Load corrected data if provided
        corrected_json = None
        if action == "MODIFIED" and corrected_file:
            try:
                with open(corrected_file, encoding="utf-8") as f:
                    corrected_json = f.read()
            except Exception as e:
                console.print(f"[red]Error reading corrected file: {e}")
                raise typer.Exit(1) from e

        with get_db_session() as session:
            manager = ReviewQueueManager(session)

            action_literal = cast(Literal["APPROVED", "REJECTED", "MODIFIED"], action)
            if manager.complete_review(
                review_id=review_id,
                action=action_literal,
                reviewer_notes=notes if notes else None,
                corrected_json=corrected_json,
            ):
                console.print(
                    f"[green]✓ Review {review_id} completed with action: {action}"
                )
            else:
                console.print(f"[red]✗ Failed to complete review {review_id}")
                raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]Error completing review: {e}")
        raise typer.Exit(1) from e


@app.command("approve")
def approve_panel(
    panel_id: str = typer.Argument(..., help="Panel ID to approve"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be approved without doing it"
    ),
) -> None:
    """Approve all pending reviews for a panel."""
    try:
        with get_db_session() as session:
            manager = ReviewQueueManager(session)

            # Get pending reviews for panel
            pending_reviews = manager.get_pending_reviews(limit=1000, panel_id=panel_id)

            if not pending_reviews:
                console.print(f"[yellow]No pending reviews for panel {panel_id}")
                return

            console.print(
                f"Found {len(pending_reviews)} pending reviews for panel {panel_id}"
            )

            if dry_run:
                console.print("[yellow]DRY RUN - No changes will be made")
                for review in pending_reviews:
                    console.print(
                        f"  Would approve: {review.review_id} - {review.sent_id}"
                    )
                return

            # Confirm approval
            if not Confirm.ask(
                f"Approve all {len(pending_reviews)} reviews for panel {panel_id}?"
            ):
                console.print("Approval cancelled")
                return

            # Approve all reviews
            approved_count = 0
            for review in pending_reviews:
                if manager.complete_review(
                    review_id=review.review_id,
                    action="APPROVED",
                    reviewer_notes=f"Bulk approved for panel {panel_id}",
                ):
                    approved_count += 1

            console.print(
                f"[green]✓ Approved {approved_count} reviews for panel {panel_id}"
            )

    except Exception as e:
        console.print(f"[red]Error approving panel: {e}")
        raise typer.Exit(1) from e


@app.command("escalate")
def escalate_stale() -> None:
    """Escalate stale reviews (older than 72 hours)."""
    try:
        with get_db_session() as session:
            manager = ReviewQueueManager(session)

            escalated_count = manager.escalate_stale_reviews()

            if escalated_count > 0:
                console.print(f"[green]✓ Escalated {escalated_count} stale reviews")
            else:
                console.print("[yellow]No stale reviews to escalate")

    except Exception as e:
        console.print(f"[red]Error escalating reviews: {e}")
        raise typer.Exit(1) from e


@app.command("export")
def export_reviews(
    output_file: str = typer.Argument(..., help="Output JSON file path"),
    status: str | None = typer.Option(None, "--status", "-s", help="Filter by status"),
    panel_id: str | None = typer.Option(
        None, "--panel", "-p", help="Filter by panel ID"
    ),
) -> None:
    """Export reviews to JSON file."""
    try:
        with get_db_session() as _:
            # Get reviews (this would need to be implemented in ReviewQueueManager)
            # For now, show placeholder
            console.print("[yellow]Export functionality would be implemented here")
            console.print(f"Would export to: {output_file}")
            console.print(f"Filters: status={status}, panel={panel_id}")

    except Exception as e:
        console.print(f"[red]Error exporting reviews: {e}")
        raise typer.Exit(1) from e


def _show_statistics(stats: dict[str, Any]) -> None:
    """Display queue statistics."""
    # Status counts
    status_table = Table(title="Review Status Counts")
    status_table.add_column("Status", style="cyan")
    status_table.add_column("Count", style="green")

    for key, value in stats.items():
        if key.startswith("count_"):
            status_name = key.replace("count_", "").upper()
            status_table.add_row(status_name, str(value))

    console.print(status_table)

    # Trigger types
    if "trigger_counts" in stats:
        trigger_table = Table(title="Trigger Types")
        trigger_table.add_column("Trigger", style="magenta")
        trigger_table.add_column("Count", style="yellow")

        for trigger, count in stats["trigger_counts"].items():
            trigger_name = trigger.replace("_", " ").title()
            trigger_table.add_row(trigger_name, str(count))

        console.print(trigger_table)

    # Other stats
    other_stats = Table(title="Other Statistics")
    other_stats.add_column("Metric", style="blue")
    other_stats.add_column("Value", style="green")

    for key, value in stats.items():
        if key not in ["trigger_counts"] and not key.startswith("count_"):
            metric_name = key.replace("_", " ").title()
            other_stats.add_row(metric_name, str(value))

    console.print(other_stats)


def _show_review_details(review: HumanReviewQueue, show_raw: bool = False) -> None:
    """Show detailed review information."""
    # Basic info
    info_table = Table(title=f"Review Details - ID: {review.review_id}")
    info_table.add_column("Field", style="cyan")
    info_table.add_column("Value", style="green")

    info_table.add_row("Sentence ID", review.sent_id)
    info_table.add_row("Panel ID", review.panel_id or "N/A")
    info_table.add_row("Speaker", review.speaker_name or "N/A")
    info_table.add_row("Country", review.country or "N/A")
    info_table.add_row("Segment ID", review.seg_id or "N/A")
    info_table.add_row("Status", review.status)
    info_table.add_row("Trigger Type", review.trigger_type)
    info_table.add_row(
        "Risk Score", str(review.ai_risk_score) if review.ai_risk_score else "N/A"
    )
    info_table.add_row("Assigned To", review.assigned_to or "N/A")
    info_table.add_row(
        "Flagged At", review.flagged_at[:19] if review.flagged_at else "N/A"
    )

    console.print(info_table)

    # AI output
    if show_raw and review.original_ai_json:
        try:
            ai_data = json.loads(review.original_ai_json)
            ai_panel = Panel(
                json.dumps(ai_data, indent=2, ensure_ascii=False),
                title="Original AI Analysis",
                expand=True,
                border_style="blue",
            )
            console.print(ai_panel)
        except json.JSONDecodeError:
            console.print("[red]Invalid JSON in AI output")

    # Reviewer notes
    if review.reviewer_notes:
        notes_panel = Panel(
            review.reviewer_notes, title="Reviewer Notes", border_style="yellow"
        )
        console.print(notes_panel)

    # Corrected data
    if review.corrected_json:
        try:
            corrected_data = json.loads(review.corrected_json)
            corrected_panel = Panel(
                json.dumps(corrected_data, indent=2, ensure_ascii=False),
                title="Corrected Analysis",
                expand=True,
                border_style="green",
            )
            console.print(corrected_panel)
        except json.JSONDecodeError:
            console.print("[red]Invalid JSON in corrected data")


if __name__ == "__main__":
    app()
