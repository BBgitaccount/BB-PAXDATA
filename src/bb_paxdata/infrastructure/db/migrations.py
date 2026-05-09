"""Alembic migration helpers."""

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def migrate() -> None:
    """Son migration'ı uygula."""
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=PROJECT_ROOT,
        check=True,
    )


def make_migration(message: str) -> None:
    """Yeni autogenerate migration oluştur."""
    subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "revision",
            "--autogenerate",
            "-m",
            message,
        ],
        cwd=PROJECT_ROOT,
        check=True,
    )


def downgrade_one() -> None:
    """Bir revision geri al."""
    subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "-1"],
        cwd=PROJECT_ROOT,
        check=True,
    )


def current() -> None:
    """Mevcut revision'ı göster."""
    subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=PROJECT_ROOT,
        check=True,
    )


def history() -> None:
    """Revision geçmişini göster."""
    subprocess.run(
        [sys.executable, "-m", "alembic", "history", "--verbose"],
        cwd=PROJECT_ROOT,
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="BB-PAXDATA migration helper")
    parser.add_argument(
        "command",
        choices=["up", "make", "down", "current", "history"],
    )
    parser.add_argument("--message", "-m", default="auto_migration")
    args = parser.parse_args()

    if args.command == "up":
        migrate()
    elif args.command == "make":
        make_migration(args.message)
    elif args.command == "down":
        downgrade_one()
    elif args.command == "current":
        current()
    else:
        history()


if __name__ == "__main__":
    main()
