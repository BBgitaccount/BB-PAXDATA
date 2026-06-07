import threading

from bb_paxdata.application.domain.models.appraisal_vector import (
    AffectType,
    AppreciationType,
    EngagementType,
    JudgmentType,
)
from bb_paxdata.application.domain.models.srl import SRLFrame, SRLSpan
from bb_paxdata.application.domain.services.appraisal_service import (
    AppraisalService,
    get_appraisal_service,
)


def test_appraisal_service_singleton():
    service1 = get_appraisal_service()
    service2 = AppraisalService()
    assert service1 is service2


def test_appraisal_service_singleton_thread_safety():
    services = []

    def get_service():
        services.append(get_appraisal_service())

    threads = [threading.Thread(target=get_service) for _ in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All instances should be exactly the same
    first_service = services[0]
    for s in services:
        assert s is first_service


def test_appraisal_service_basic_detection():
    service = get_appraisal_service()
    text = "We are happy and secure today."
    vector = service.analyze(text)
    assert vector.affect_score > 0.0
    assert (
        vector.affect_type == AffectType.SECURITY
    )  # "secure" (0.7) > "happy" (0.6) absolute score priority
    assert "happy" in vector.trigger_words
    assert "secure" in vector.trigger_words


def test_appraisal_service_subphrase_collision():
    service = get_appraisal_service()
    # "deeply concerned" matches AFFECT (-0.7).
    # If subphrase collision prevention is working correctly, it should NOT match "concerned" separately.
    vector = service.analyze("We are deeply concerned about the situation.")
    assert vector.affect_score == -0.7
    assert vector.affect_type == AffectType.SECURITY
    assert "deeply concerned" in vector.trigger_words
    assert (
        "concerned" not in vector.trigger_words
    )  # Should be subsumed by "deeply concerned"


def test_appraisal_service_lexicon_exclusivity():
    service = get_appraisal_service()
    # "unacceptable" must only trigger JUDGMENT (sanction), not APPRECIATION.
    # "effective" must only trigger APPRECIATION (value), not JUDGMENT.
    v_unacceptable = service.analyze("This behavior is unacceptable.")
    assert v_unacceptable.judgment_score == -0.7
    assert v_unacceptable.judgment_type == JudgmentType.SANCTION
    assert v_unacceptable.judgment_is_sanction is True
    assert v_unacceptable.appreciation_score == 0.0

    v_effective = service.analyze("The measures are very effective.")
    assert v_effective.appreciation_score == 0.5
    assert v_effective.appreciation_type == AppreciationType.VALUE
    assert v_effective.judgment_score == 0.0


def test_appraisal_service_graduation_and_srl_boost():
    service = get_appraisal_service()
    # Test graduation force direction
    v_grad = service.analyze("This is extremely important.")
    assert v_grad.graduation_force > 0.0
    assert v_grad.graduation_force_direction == "up"

    # Test SRL boost (argm_mod modal verbs)
    srl_modal_up = SRLFrame(
        verb="act",
        arg0=SRLSpan(text="actor", start_char=0, end_char=5),
        argm_mod="must",
    )
    v_boost_up = service.analyze("We act.", srl_frame=srl_modal_up)
    assert v_boost_up.graduation_force_direction == "up"
    assert v_boost_up.graduation_force == 0.2  # config default boost is 0.2

    srl_modal_down = SRLFrame(
        verb="act",
        arg0=SRLSpan(text="actor", start_char=0, end_char=5),
        argm_mod="might",
    )
    v_boost_down = service.analyze("We act.", srl_frame=srl_modal_down)
    assert v_boost_down.graduation_force_direction == "down"
    assert v_boost_down.graduation_force == 0.1


def test_appraisal_service_default_engagement():
    service = get_appraisal_service()
    # When no engagement keywords or hedging markers exist, default to monogloss with 0.0 confidence
    vector = service.analyze("The sky is blue.")
    assert vector.engagement_type == EngagementType.MONOGLOSS
    assert vector.engagement_confidence == 0.0

    # With hedging markers, should be heterogloss
    vector_hedge = service.analyze(
        "The sky is blue.", hedging_detected_markers=["perhaps"]
    )
    assert vector_hedge.engagement_type == EngagementType.HETEROGLOSS
    assert vector_hedge.engagement_confidence > 0.0
