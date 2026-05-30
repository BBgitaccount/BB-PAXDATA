# scratch/list_python_blobs.py
import subprocess


def main():
    out = subprocess.check_output(["git", "fsck", "--lost-found"], text=True)
    blobs = [line.split()[2] for line in out.splitlines() if "dangling blob" in line]
    print(f"Checking {len(blobs)} blobs...")

    with open("scratch/python_blobs.txt", "w", encoding="utf-8") as f:
        for b in blobs:
            c = subprocess.check_output(["git", "cat-file", "-p", b])
            if b"class " in c or b"def " in c:
                try:
                    text = c.decode("utf-8", errors="replace")
                    first_lines = [
                        line.strip() for line in text.splitlines()[:5] if line.strip()
                    ]
                    first_few = " | ".join(first_lines)
                    f.write(
                        f"Blob: {b} | Size: {len(c)} bytes | Lines: {len(text.splitlines())}\n"
                    )
                    f.write(f"  First few lines: {first_few[:200]}\n")
                except Exception as e:
                    f.write(f"Blob: {b} | Error decoding: {e}\n")


if __name__ == "__main__":
    main()
