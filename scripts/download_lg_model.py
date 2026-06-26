import os
import sys
import urllib.request


def progress_callback(count, block_size, total_size):
    percent = int(count * block_size * 100 / total_size)
    percent = min(100, percent)
    sys.stdout.write(
        f"\rDownloading: {percent}% ({count * block_size / 1024 / 1024:.2f} MB / {total_size / 1024 / 1024:.2f} MB)"
    )
    sys.stdout.flush()


def main():
    url = "https://github.com/explosion/spacy-models/releases/download/en_core_web_lg-3.8.0/en_core_web_lg-3.8.0-py3-none-any.whl"
    out_dir = "docker/models"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "en_core_web_lg-3.8.0-py3-none-any.whl")

    if os.path.exists(out_path):
        os.remove(out_path)

    print(f"Starting download from {url} to {out_path}...")
    try:
        urllib.request.urlretrieve(url, out_path, reporthook=progress_callback)
        print("\nDownload completed successfully!")
    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
