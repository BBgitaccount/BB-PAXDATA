import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bb_paxdata.config.settings import get_settings


def print_settings():
    settings = get_settings()
    print("Database URL:", settings.database_url)
    print("Database Path:", settings.database_path)
    print("Is Async DB:", settings.is_async_db)


if __name__ == "__main__":
    print_settings()
