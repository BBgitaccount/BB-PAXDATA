import subprocess
import sys

MODELS = {
    "tr_core_news_lg": "https://huggingface.co/turkish-nlp-suite/tr_core_news_lg/resolve/main/tr_core_news_lg-1.0-py3-none-any.whl",
    "en_core_web_lg": "en_core_web_lg",
}


def download_models() -> None:
    """Download the configured SpaCy models."""
    print("Starting SpaCy model downloads...")
    for model_name, source in MODELS.items():
        print(f"Installing {model_name}...")
        try:
            if source.startswith("http"):
                # Install from URL
                subprocess.check_call([sys.executable, "-m", "pip", "install", source])
            else:
                # Install via spacy download
                subprocess.check_call(
                    [sys.executable, "-m", "spacy", "download", source]
                )
            print(f"Successfully installed {model_name}")
        except subprocess.CalledProcessError as e:
            print(f"Error installing {model_name}: {e}")
            sys.exit(1)
    print("All models installed successfully.")


if __name__ == "__main__":
    download_models()
