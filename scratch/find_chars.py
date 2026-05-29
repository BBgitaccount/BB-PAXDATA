import os

files = [
    "src/bb_paxdata/interfaces/cli/commands/build.py",
    "src/bb_paxdata/interfaces/cli/commands/validate.py",
    "src/bb_paxdata/interfaces/cli/commands/review.py",
    "src/bb_paxdata/interfaces/cli/commands/analyze.py",
]

output = []
for fpath in files:
    if os.path.exists(fpath):
        with open(fpath, encoding="utf-8") as f:
            lines = f.readlines()
        for idx, line in enumerate(lines):
            if "✓" in line or "⚠️" in line:
                ascii_line = line.replace("✓", "[OK]").replace("⚠️", "[WARN]").strip()
                output.append(f"{fpath}:{idx+1}: {ascii_line}")

with open("scratch/chars_found.txt", "w", encoding="utf-8") as out_f:
    out_f.write("\n".join(output) + "\n")

print(f"Results written to scratch/chars_found.txt. Found {len(output)} lines.")
