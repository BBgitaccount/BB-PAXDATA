"""
Configuration for SpaCy models and pipelines in BB-PAXDATA.
"""

from typing import TypedDict


class PipelineConfig(TypedDict):
    model: str
    components: list[str]
    disabled: list[str]


# SpaCy pipeline configuration
# Defines which models to use and which components to disable for performance.
SPACY_PIPELINES: dict[str, PipelineConfig] = {
    "tr": {
        "model": "tr_core_news_md",
        "components": [
            "tok2vec",
            "tagger",
            "parser",
            "ner",
            "attribute_ruler",
            "lemmatizer",
        ],
        "disabled": [],
    },
    "en": {
        "model": "en_core_web_lg",
        "components": [
            "tok2vec",
            "tagger",
            "parser",
            "ner",
            "attribute_ruler",
            "lemmatizer",
        ],
        "disabled": [],
    },
}
