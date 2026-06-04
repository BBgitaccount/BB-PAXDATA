from bb_paxdata.application.pipeline.configurator import PipelineConfigurator


def test_pipeline_configurator_fallback() -> None:
    """Test that configurator falls back to default settings if config file does not exist."""
    configurator = PipelineConfigurator(config_path="nonexistent_config.yaml")

    config = configurator.get_config("default")
    assert "stages" in config
    assert "collect" in config
    assert "pre_process" in config["stages"]
    assert "collect" in config["stages"]
    assert "ner" in config["collect"]["services"]
    assert "tokenizer" in config["collect"]["services"]


def test_pipeline_configurator_variants() -> None:
    """Test retrieval of different pipeline variants."""
    configurator = PipelineConfigurator()

    # 1. Default variant
    default_config = configurator.get_config("default")
    assert len(default_config["stages"]) == 6
    assert "dual_gate" in default_config["stages"]

    # 2. Fast mode variant
    fast_config = configurator.get_config("fast_mode")
    assert "dual_gate" not in fast_config["stages"]
    assert "topic_modeling" not in fast_config["collect"]["services"]
    assert fast_config["detect"]["fail_fast_on_missing_ai"] is True

    # 3. Invalid variant fallback to default
    invalid_config = configurator.get_config("invalid_variant_name")
    assert invalid_config == default_config
