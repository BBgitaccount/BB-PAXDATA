import sys
from pathlib import Path

# Add src to python path to import project modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bb_paxdata.interfaces.cli.commands.build import (
    PANELS_METADATA,
    standardize_file_content,
)


def main():
    data_dir = Path("data/Antalya Diplomatic Forum 2026")
    processed = 0
    logs = []

    for file_path in data_dir.rglob("*.txt"):
        name = file_path.name
        if name not in PANELS_METADATA:
            continue

        logs.append(f"Standardizing: {name}")

        with open(file_path, encoding="utf-8") as f:
            raw_content = f.read()

        standardized_content = standardize_file_content(file_path, raw_content)

        if raw_content != standardized_content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(standardized_content)
            processed += 1

    logs.append(f"Successfully standardized {processed} files.")

    # Save log file
    with open("scratch/standardize_log.txt", "w", encoding="utf-8") as log_file:
        log_file.write("\n".join(logs))
    print(f"Successfully standardized {processed} files.")


if __name__ == "__main__":
    main()
