import subprocess
import sys

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


def run_command(args: list[str]) -> None:
    print(f"\n> Running: {' '.join(args)}")
    try:
        subprocess.run(args, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")
        sys.exit(1)


def main() -> None:
    print("=== STARTING BB-PAXDATA PIPELINE ===")

    # 1. Install dependencies
    print("\n--- Step 1: Installing Dependencies ---")
    run_command(["poetry", "install"])

    # 2. Download SpaCy models
    print("\n--- Step 2: Downloading SpaCy Models ---")
    run_command(["poetry", "run", "python", "scripts/download_spacy_models.py"])

    # 3. Database migrations (Database initialization)
    print("\n--- Step 3: Running Database Migrations ---")
    run_command(["poetry", "run", "alembic", "upgrade", "head"])

    # 4. Build database from transcripts (Logic-only, AI-free mode)
    print("\n--- Step 4: Building Database from Transcripts (Logic-Only) ---")
    run_command(
        [
            "poetry",
            "run",
            "bbpaxdata",
            "build",
            "build",
            "data/Antalya Diplomatic Forum 2026",
            "--logic-only",
            "--force-rebuild",
        ]
    )

    # 5. Run full analysis for all panels
    print("\n--- Step 5: Running Full Analysis on all 12 Panels ---")
    for panel in PANELS:
        print(f"\n>>> Analyzing Panel: {panel}")
        run_command(
            ["poetry", "run", "bbpaxdata", "analyze", "full", "--panel-id", panel]
        )

    print("\n=== PIPELINE RUN COMPLETED SUCCESSFULLY ===")


if __name__ == "__main__":
    main()
