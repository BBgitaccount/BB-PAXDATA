"""Tokenizer special cases for diplomatic Latin expressions.

Custom tokenizer special cases for Latin diplomatic expressions → single tokens.
"""

SPECIAL_CASES = {
    "inter alia": [{"ORTH": "inter alia"}],
    "mutatis mutandis": [{"ORTH": "mutatis mutandis"}],
    "erga omnes": [{"ORTH": "erga omnes"}],
    "jus cogens": [{"ORTH": "jus cogens"}],
    "pacta sunt servanda": [{"ORTH": "pacta sunt servanda"}],
    "rebus sic stantibus": [{"ORTH": "rebus sic stantibus"}],
}


def add_special_cases(nlp):
    """Add diplomatic Latin special cases to spaCy tokenizer.

    Args:
        nlp: spaCy Language object
    """
    for text, pattern in SPECIAL_CASES.items():
        nlp.tokenizer.add_special_case(text, pattern)
