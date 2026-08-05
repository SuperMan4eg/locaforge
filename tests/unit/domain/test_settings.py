import pytest

from locaforge.domain.settings import ModelSettings


def test_model_settings_validate_runtime_limits() -> None:
    with pytest.raises(ValueError, match="Model name"):
        ModelSettings(model=" ")
    with pytest.raises(ValueError, match="timeout"):
        ModelSettings(timeout_seconds=0)
    with pytest.raises(ValueError, match="Batch size"):
        ModelSettings(batch_size=0)


def test_model_settings_round_trip_mapping() -> None:
    settings = ModelSettings(
        "qwen3:8b", 90.0, 12, "Use game terminology.", "Check meaning carefully."
    )

    assert ModelSettings.from_mapping(settings.to_dict()) == settings


def test_old_model_settings_receive_default_review_prompt() -> None:
    settings = ModelSettings.from_mapping({"model": "qwen3:8b"})

    assert settings.review_prompt
