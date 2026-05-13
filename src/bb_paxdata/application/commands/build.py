"""Build database command with duplicate protection and quality integration."""

import hashlib
import sys
from datetime import datetime
from pathlib import Path

import structlog
import typer
from rich.console import Console

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from bb_paxdata.infrastructure.db.models import Panel
from bb_paxdata.infrastructure.db.processed_files import ProcessedFile
from bb_paxdata.infrastructure.db.session import get_db_session
from bb_paxdata.quality.data_contract import DataContractValidator
from bb_paxdata.quality.violations import ViolationLogger

logger = structlog.get_logger(__name__)
console = Console()

app = typer.Typer(help="Build database from transcript files")


def calculate_idempotency_key(
    file_content: str,
    file_name: str,
    parser_version: str = "5.8",
    speaker_map_version: str = "1.0",
) -> str:
    """Calculate idempotency key for file processing."""
    content_hash = hashlib.sha256(file_content.encode("utf-8")).hexdigest()
    key_string = f"{content_hash}{file_name}{parser_version}{speaker_map_version}"
    return hashlib.sha256(key_string.encode("utf-8")).hexdigest()


def get_parser_version() -> str:
    """Get current parser version."""
    return "5.8"  # Should match AIanalyst_v5_8 version


def get_speaker_map_version() -> str:
    """Get speaker map version hash."""
    # This would calculate hash of SPEAKER_MAP configuration
    # For now, return a placeholder
    return "1.0"


@app.command()
def build(
    data_dir: str = typer.Argument(..., help="Directory containing transcript files"),
    force_rebuild: bool = typer.Option(
        False, "--force-rebuild", "-f", help="Force rebuild even if already processed"
    ),
    panel_filter: str | None = typer.Option(
        None, "--panel", "-p", help="Process only specific panel"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-d", help="Show what would be processed without doing it"
    ),
) -> None:
    """Build database from transcript files with duplicate protection."""
    try:
        data_path = Path(data_dir)
        if not data_path.exists():
            console.print(f"[red]Data directory not found: {data_dir}")
            raise typer.Exit(1)

        # Initialize components
        validator = DataContractValidator()
        violation_logger = ViolationLogger()

        with get_db_session() as session:
            processed_count = 0
            skipped_count = 0
            error_count = 0

            # Find transcript files
            transcript_files = list(data_path.glob("*.txt"))
            if panel_filter:
                transcript_files = [
                    f for f in transcript_files if panel_filter in f.name
                ]

            console.print(f"Found {len(transcript_files)} transcript files")

            for file_path in transcript_files:
                try:
                    # Read file content
                    with open(file_path, encoding="utf-8") as f:
                        file_content = f.read()

                    # Calculate idempotency key
                    idempotency_key = calculate_idempotency_key(
                        file_content,
                        file_path.name,
                        get_parser_version(),
                        get_speaker_map_version(),
                    )

                    # Check if already processed
                    existing = (
                        session.query(ProcessedFile)
                        .filter(ProcessedFile.idempotency_key == idempotency_key)
                        .first()
                    )

                    if existing and not force_rebuild and existing.force_rebuild == 0:
                        console.print(
                            f"[yellow]⏭️  Skipping {file_path.name} (already processed)"
                        )
                        skipped_count += 1
                        continue

                    # Validate input
                    validation_result = validator.validate_transcript_input(
                        file_content, file_path
                    )
                    if not validation_result.passed:
                        console.print(
                            f"[red]❌ Input validation failed for {file_path.name}"
                        )
                        violation_logger.log_input_violation(
                            str(file_path),
                            validation_result.details.get("failed_checks", []),
                        )
                        error_count += 1
                        continue

                    if dry_run:
                        console.print(f"[cyan]🔍 Would process: {file_path.name}")
                        console.print(f"   Idempotency key: {idempotency_key[:16]}...")
                        processed_count += 1
                        continue

                    # Process file (this would call the actual processing logic)
                    console.print(f"[green]📝 Processing: {file_path.name}")

                    # TODO: Call actual file processing
                    # processed_data = process_transcript_file(file_content, file_path)

                    # Update processed files tracking
                    if existing:
                        existing.reprocess_count += 1
                        existing.last_processed_at = datetime.utcnow()
                        if force_rebuild:
                            existing.force_rebuild = 0
                    else:
                        processed_file = ProcessedFile(
                            file_hash=hashlib.sha256(
                                file_content.encode("utf-8")
                            ).hexdigest(),
                            file_name=file_path.name,
                            file_size_bytes=len(file_content.encode("utf-8")),
                            idempotency_key=idempotency_key,
                            parser_version=get_parser_version(),
                            speaker_map_version=get_speaker_map_version(),
                            first_processed_at=datetime.utcnow(),
                            last_processed_at=datetime.utcnow(),
                            reprocess_count=0,
                            force_rebuild=0,
                        )
                        session.add(processed_file)

                    session.commit()
                    processed_count += 1

                except Exception as e:
                    console.print(f"[red]❌ Error processing {file_path.name}: {e}")
                    logger.error(
                        f"Error processing file {file_path.name}", error=str(e)
                    )
                    error_count += 1
                    session.rollback()
                    continue

            # Summary
            console.print("\n[green]✅ Build completed!")
            console.print(f"Processed: {processed_count}")
            console.print(f"Skipped: {skipped_count}")
            console.print(f"Errors: {error_count}")

            if dry_run:
                console.print("[yellow]DRY RUN - No files were actually processed")

    except Exception as e:
        console.print(f"[red]Build failed: {e}")
        logger.error("Build command failed", error=str(e))
        raise typer.Exit(1) from e


@app.command("status")
def status(
    file_path: str = typer.Argument(..., help="Path to transcript file")
) -> None:
    """Check processing status of a specific file."""
    try:
        path = Path(file_path)
        if not path.exists():
            console.print(f"[red]File not found: {file_path}")
            raise typer.Exit(1)

        # Read file content
        with open(path, encoding="utf-8") as f:
            file_content = f.read()

        # Calculate idempotency key
        idempotency_key = calculate_idempotency_key(
            file_content, path.name, get_parser_version(), get_speaker_map_version()
        )

        with get_db_session() as session:
            # Check processed files
            processed = (
                session.query(ProcessedFile)
                .filter(ProcessedFile.idempotency_key == idempotency_key)
                .first()
            )

            # Check panels
            file_hash = hashlib.sha256(file_content.encode("utf-8")).hexdigest()
            panels = session.query(Panel).filter(Panel.file_hash == file_hash).all()

            console.print(f"File: {path.name}")
            console.print(f"Size: {len(file_content)} characters")
            console.print(f"Idempotency key: {idempotency_key}")
            console.print(f"File hash: {file_hash}")

            if processed:
                console.print(f"[green]✅ Processed: {processed.first_processed_at}")
                console.print(f"Reprocess count: {processed.reprocess_count}")
                console.print(f"Last processed: {processed.last_processed_at}")
                console.print(f"Parser version: {processed.parser_version}")
                console.print(f"Speaker map version: {processed.speaker_map_version}")
            else:
                console.print("[yellow]⏳ Not processed yet")

            if panels:
                console.print(f"Associated panels: {len(panels)}")
                for panel in panels:
                    status = "Active" if getattr(panel, "is_active", 1) else "Inactive"
                    console.print(f"  - {panel.panel_id} ({status})")
            else:
                console.print("No associated panels found")

    except Exception as e:
        console.print(f"[red]Status check failed: {e}")
        logger.error("Status command failed", error=str(e))
        raise typer.Exit(1) from e


@app.command("clean")
def clean(
    panel_id: str | None = typer.Option(
        None, "--panel", "-p", help="Clean specific panel"
    ),
    older_than: int | None = typer.Option(
        None, "--older-than", "-o", help="Clean entries older than N days"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force cleanup without confirmation"
    ),
) -> None:
    """Clean processed files and panels."""
    try:
        with get_db_session() as session:
            if panel_id:
                # Clean specific panel
                panels = (
                    session.query(Panel)
                    .filter(Panel.panel_id.like(f"%{panel_id}%"))
                    .all()
                )

                if not panels:
                    console.print(f"[yellow]No panels found matching: {panel_id}")
                    return

                if not force:
                    if not typer.confirm(
                        f"Delete {len(panels)} panels matching '{panel_id}'?"
                    ):
                        console.print("Cleanup cancelled")
                        return

                for panel in panels:
                    session.delete(panel)

                console.print(f"[green]✅ Deleted {len(panels)} panels")

            elif older_than:
                # Clean old processed files
                # This would require adding timestamp columns to processed_files
                console.print("[yellow]Age-based cleanup not yet implemented")

            else:
                console.print("[red]Must specify either --panel or --older-than")
                raise typer.Exit(1)

            session.commit()

    except Exception as e:
        console.print(f"[red]Cleanup failed: {e}")
        logger.error("Clean command failed", error=str(e))
        raise typer.Exit(1) from e


if __name__ == "__main__":
    app()
