"""
Unit tests for presupposition trigger lexicon.
"""

from bb_paxdata.application.domain.lexicons.presupposition_triggers import (
    PresuppositionLexicon,
)
from bb_paxdata.application.domain.models.presupposition import TriggerType


def test_lexicon_load_default():
    """Test loading default English lexicon."""
    lexicon = PresuppositionLexicon.load_default()
    assert lexicon._language == "en"


def test_lexicon_for_language():
    """Test loading lexicon for specific language."""
    en_lexicon = PresuppositionLexicon.for_language("en")
    assert en_lexicon._language == "en"

    tr_lexicon = PresuppositionLexicon.for_language("tr")
    assert tr_lexicon._language == "tr"


def test_lexicon_get_triggers():
    """Test getting triggers for specific type."""
    lexicon = PresuppositionLexicon.for_language("en")

    factive_triggers = lexicon.get_triggers(TriggerType.FACTIVE_VERB)
    assert "know" in factive_triggers
    assert "realize" in factive_triggers
    assert "regret" in factive_triggers

    temporal_triggers = lexicon.get_triggers(TriggerType.TEMPORAL_ADVERB)
    assert "still" in temporal_triggers
    assert "again" in temporal_triggers


def test_lexicon_is_trigger():
    """Test checking if a word is a trigger."""
    lexicon = PresuppositionLexicon.for_language("en")

    assert lexicon.is_trigger("know", TriggerType.FACTIVE_VERB)
    assert lexicon.is_trigger("realize", TriggerType.FACTIVE_VERB)
    assert not lexicon.is_trigger("run", TriggerType.FACTIVE_VERB)


def test_lexicon_is_any_trigger():
    """Test checking if a word is any type of trigger."""
    lexicon = PresuppositionLexicon.for_language("en")

    assert lexicon.is_any_trigger("know")
    assert lexicon.is_any_trigger("still")
    assert lexicon.is_any_trigger("stop")
    assert not lexicon.is_any_trigger("hello")


def test_lexicon_get_trigger_type():
    """Test getting trigger type for a word."""
    lexicon = PresuppositionLexicon.for_language("en")

    assert lexicon.get_trigger_type("know") == TriggerType.FACTIVE_VERB
    assert lexicon.get_trigger_type("still") == TriggerType.TEMPORAL_ADVERB
    assert lexicon.get_trigger_type("stop") == TriggerType.CHANGE_OF_STATE
    assert lexicon.get_trigger_type("hello") is None


def test_lexicon_turkish_triggers():
    """Test Turkish trigger lexicon."""
    lexicon = PresuppositionLexicon.for_language("tr")

    factive_triggers = lexicon.get_triggers(TriggerType.FACTIVE_VERB)
    assert "biliyor" in factive_triggers
    assert "fark ediyor" in factive_triggers

    temporal_triggers = lexicon.get_triggers(TriggerType.TEMPORAL_ADVERB)
    assert "hâlâ" in temporal_triggers
    assert "yine" in temporal_triggers


def test_lexicon_get_all_triggers():
    """Test getting all trigger types."""
    lexicon = PresuppositionLexicon.for_language("en")

    all_triggers = lexicon.get_all_triggers()
    assert TriggerType.FACTIVE_VERB in all_triggers
    assert TriggerType.IMPLICATIVE_VERB in all_triggers
    assert TriggerType.TEMPORAL_ADVERB in all_triggers
    assert TriggerType.CHANGE_OF_STATE in all_triggers


def test_lexicon_multiword_patterns():
    """Test multiword trigger patterns."""
    lexicon = PresuppositionLexicon.for_language("en")

    patterns = lexicon.get_multiword_patterns()
    assert "no longer" in patterns

    tr_lexicon = PresuppositionLexicon.for_language("tr")
    tr_patterns = tr_lexicon.get_multiword_patterns()
    # Turkish patterns are minimal per spec
    assert isinstance(tr_patterns, list)


def test_lexicon_case_insensitive():
    """Test that trigger matching is case-insensitive."""
    lexicon = PresuppositionLexicon.for_language("en")

    assert lexicon.is_trigger("KNOW", TriggerType.FACTIVE_VERB)
    assert lexicon.is_trigger("Know", TriggerType.FACTIVE_VERB)
    assert lexicon.is_trigger("kNoW", TriggerType.FACTIVE_VERB)
