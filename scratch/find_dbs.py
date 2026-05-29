import glob
from pathlib import Path


def find_db_files():
    print("Recurse searching for DB files:")
    for path in glob.glob("**/*.db", recursive=True):
        p = Path(path)
        print(f"  {p}: size={p.stat().st_size} bytes")
    for path in glob.glob("**/*.db.bak", recursive=True):
        p = Path(path)
        print(f"  {p}: size={p.stat().st_size} bytes")


if __name__ == "__main__":
    find_db_files()
