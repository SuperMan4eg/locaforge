import pytest

from locaforge.domain.settings import ModelSettings


def test_model_settings_validate_runtime_limits() -> None:
    with pytest.raises(ValueError, match="Model name"):
        ModelSettings(model=" ")
    with pytest.raises(ValueError, match="timeout"):
        ModelSettings(timeout_seconds=0)
    with pytest.raises(ValueError, match="Batch size"):
        ModelSettings(batch_size=0)
    with pytest.raises(ValueError, match="keep-alive"):
        ModelSettings(keep_alive_seconds=-2)


def test_model_settings_round_trip_mapping() -> None:
    settings = ModelSettings(
        "qwen3:8b", 90.0, 12, "Use game terminology.", "Check meaning carefully."
    )

    assert ModelSettings.from_mapping(settings.to_dict()) == settings


def test_old_model_settings_receive_default_review_prompt() -> None:
    settings = ModelSettings.from_mapping({"model": "qwen3:8b"})

    assert settings.review_prompt
    assert settings.effective_review_model == "qwen3:8b"


def test_model_settings_support_separate_reviewer_model() -> None:
    settings = ModelSettings(model="translator", review_model="reviewer")

    assert settings.effective_review_model == "reviewer"
    assert ModelSettings.from_mapping(settings.to_dict()) == settings


def test_model_settings_store_separate_reasoning_modes() -> None:
    settings = ModelSettings(
        translation_reasoning="low",
        review_reasoning="high",
    )

    assert ModelSettings.from_mapping(settings.to_dict()) == settings
    with pytest.raises(ValueError, match="translation reasoning"):
        ModelSettings(translation_reasoning="maximum")


def test_model_settings_store_ollama_keep_alive() -> None:
    settings = ModelSettings(keep_alive_seconds=-1)

    assert ModelSettings.from_mapping(settings.to_dict()) == settings
    assert ModelSettings.from_mapping({"keep_alive_seconds": -2}).keep_alive_seconds == 300
