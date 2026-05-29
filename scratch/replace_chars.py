import os

files = [
    "src/bb_paxdata/interfaces/cli/commands/build.py",
    "src/bb_paxdata/interfaces/cli/commands/validate.py",
    "src/bb_paxdata/interfaces/cli/commands/analyze.py",
    "src/bb_paxdata/interfaces/cli/review.py",
]

for fpath in files:
    if os.path.exists(fpath):
        with open(fpath, encoding="utf-8") as f:
            content = f.read()

        replaced_content = content.replace("✓", "[OK]").replace("⚠️", "[WARN]")

        with open(fpath, "w", encoding="utf-8") as f:
            f.write(replaced_content)

        print(f"Replaced symbols in {fpath}")
    else:
        print(f"File not found: {fpath}")
