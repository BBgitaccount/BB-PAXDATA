from bb_paxdata.domain.models.analysis import Analysis
from bb_paxdata.domain.models.sentence import Sentence
from bb_paxdata.domain.utils.hash import generate_sentence_code


def test_generate_sentence_code():
    code1 = generate_sentence_code()
    code2 = generate_sentence_code()

    assert code1.startswith("S_")
    assert len(code1) == 10  # "S_" + 8 characters
    assert code1 != code2  # Uniqueness

    # Assert character structure
    alphanumeric_part = code1[2:]
    assert alphanumeric_part.isalnum()
    assert alphanumeric_part.isupper() or alphanumeric_part.isdigit()


def test_sentence_model_auto_generates_code():
    sentence = Sentence(id="sent-1", text="Hello world")
    assert sentence.sentence_code is not None
    assert sentence.sentence_code.startswith("S_")
    assert len(sentence.sentence_code) == 10


def test_sentence_model_retains_provided_code():
    sentence = Sentence(id="sent-1", text="Hello world", sentence_code="S_MYCODE12")
    assert sentence.sentence_code == "S_MYCODE12"


def test_analysis_model_accepts_sentence_code():
    analysis = Analysis(sentence_id="sent-1", sentence_code="S_XYZ789")
    assert analysis.sentence_code == "S_XYZ789"
