from pathlib import Path


def main():
    data_dir = Path("data/Antalya Diplomatic Forum 2026")
    speakers = set()
    for file_path in data_dir.rglob("*.txt"):
        with open(file_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if " : " in line:
                    speaker = line.split(" : ", 1)[0].strip()
                    speakers.add(speaker)
                elif ":" in line:
                    speaker = line.split(":", 1)[0].strip()
                    speakers.add(speaker)

    out_path = Path("scratch/speakers.txt")
    with open(out_path, "w", encoding="utf-8") as out:
        out.write("Found unique speakers:\n")
        for s in sorted(speakers):
            out.write(f"- {s}\n")
    print(f"Speakers list written to {out_path}")


if __name__ == "__main__":
    main()
