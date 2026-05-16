from bb_paxdata.domain.enums.frame_type import FrameType


def test_frame_type_academic_values():
    assert FrameType.PROBLEM_DEFINITION == "problem_definition"
    assert FrameType.EPISODIC == "episodic"
    assert FrameType.THEMATIC == "thematic"


def test_frame_type_properties():
    assert FrameType.PROBLEM_DEFINITION.is_entman_function is True
    assert FrameType.EPISODIC.is_iyengar_dimension is True
    assert FrameType.THEMATIC.is_iyengar_dimension is True
    assert FrameType.SECURITY_FRAME.is_entman_function is False


def test_frame_type_entman_function_placeholder():
    # Currently returns None as per requirement
    assert FrameType.EPISODIC.entman_function is None
