"""Prepare spaCy training data in DocBin format.

Builds DocBin files for train/dev/test splits from annotated data.
"""

import json
from pathlib import Path

import spacy
from spacy.tokens import DocBin


def prepare_training_data(
    raw_data_path: str,
    output_dir: str = "./data",
    train_ratio: float = 0.7,
    dev_ratio: float = 0.15,
) -> None:
    """Prepare spaCy training data in DocBin format.

    Args:
        raw_data_path: Path to JSON file with annotated data
        output_dir: Output directory for DocBin files
        train_ratio: Ratio for training split (default: 0.7)
        dev_ratio: Ratio for dev split (default: 0.15)
    """
    # Load raw annotated data
    with open(raw_data_path, encoding="utf-8") as f:
        raw_data = json.load(f)

    # Split data
    n = len(raw_data)
    train_end = int(n * train_ratio)
    dev_end = int(n * (train_ratio + dev_ratio))

    train_data = raw_data[:train_end]
    dev_data = raw_data[train_end:dev_end]
    test_data = raw_data[dev_end:]

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Build DocBin for each split
    nlp = spacy.blank("en")

    # Add special cases for diplomatic Latin
    from bb_paxdata.infrastructure.nlp.tokenizer_rules import add_special_cases

    add_special_cases(nlp)

    # Train split
    db_train = DocBin()
    for text, annotations in train_data:
        doc = nlp.make_doc(text)
        ents = []
        for start, end, label in annotations["entities"]:
            span = doc.char_span(start, end, label=label)
            if span is None:
                print(f"Skipping misaligned entity: {text[start:end]!r}")
                continue
            ents.append(span)
        doc.ents = ents
        db_train.add(doc)

    db_train.to_disk(output_path / "train.spacy")
    print(f"Train split: {len(train_data)} samples → {output_path / 'train.spacy'}")

    # Dev split
    db_dev = DocBin()
    for text, annotations in dev_data:
        doc = nlp.make_doc(text)
        ents = []
        for start, end, label in annotations["entities"]:
            span = doc.char_span(start, end, label=label)
            if span is None:
                print(f"Skipping misaligned entity: {text[start:end]!r}")
                continue
            ents.append(span)
        doc.ents = ents
        db_dev.add(doc)

    db_dev.to_disk(output_path / "dev.spacy")
    print(f"Dev split: {len(dev_data)} samples → {output_path / 'dev.spacy'}")

    # Test split
    db_test = DocBin()
    for text, annotations in test_data:
        doc = nlp.make_doc(text)
        ents = []
        for start, end, label in annotations["entities"]:
            span = doc.char_span(start, end, label=label)
            if span is None:
                print(f"Skipping misaligned entity: {text[start:end]!r}")
                continue
            ents.append(span)
        doc.ents = ents
        db_test.add(doc)

    db_test.to_disk(output_path / "test.spacy")
    print(f"Test split: {len(test_data)} samples → {output_path / 'test.spacy'}")

    print("\nTraining data preparation completed!")
    print(f"Total samples: {n}")
    print(f"Train: {len(train_data)}, Dev: {len(dev_data)}, Test: {len(test_data)}")


if __name__ == "__main__":
    # Example usage
    # This requires a JSON file with annotated data in the format:
    # [
    #   ["Text with entities", {"entities": [[start, end, "LABEL"], ...]}],
    #   ...
    # ]

    # For demonstration, create a sample
    sample_data = [
        [
            "The Russian Federation supports the UN Security Council resolution.",
            {
                "entities": [
                    [4, 21, "COUNTRY"],
                    [35, 51, "INSTITUTION"],
                    [52, 71, "RESOLUTION"],
                ]
            },
        ],
        [
            "Ambassador Smith from the United States emphasized jus cogens.",
            {
                "entities": [
                    [0, 20, "ACTOR"],
                    [30, 44, "COUNTRY"],
                    [55, 65, "LEGAL_TERM"],
                ]
            },
        ],
    ]

    # Write sample data
    sample_path = Path("./data/sample_annotated.json")
    sample_path.parent.mkdir(parents=True, exist_ok=True)
    with open(sample_path, "w", encoding="utf-8") as f:
        json.dump(sample_data, f, indent=2)

    # Prepare training data
    prepare_training_data(str(sample_path))
