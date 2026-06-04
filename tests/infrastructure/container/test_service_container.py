from bb_paxdata.infrastructure.container.service_container import ServiceContainer


def test_service_container_singleton() -> None:
    """Test that ServiceContainer follows the singleton pattern."""
    # Reset instance first to ensure clean state
    ServiceContainer._instance = None

    container1 = ServiceContainer.get_instance(logic_mode=True)
    container2 = ServiceContainer.get_instance()

    assert container1 is container2
    assert container1._logic_mode is True


def test_service_container_initialization() -> None:
    """Test that all essential services are initialized."""
    ServiceContainer._instance = None
    container = ServiceContainer.get_instance(logic_mode=True)

    assert container.language_detector is not None
    assert container.ner_service is not None
    assert container.tokenizer_service is not None
    assert container.prompt_registry is not None
    assert container.ai_analyst is not None
