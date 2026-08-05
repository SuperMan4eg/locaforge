import pytest

from locaforge.application.errors import PlaceholderMismatchError
from locaforge.application.services.placeholder_protector import PlaceholderProtector


def test_protects_and_restores_supported_placeholder_types() -> None:
    source = "Hello {name}, score: %03d\\n<b>level</b>"

    protected = PlaceholderProtector().protect(source)

    assert protected.protected != source
    assert protected.restore(protected.protected.replace("Hello", "Привет")) == (
        "Привет {name}, score: %03d\\n<b>level</b>"
    )


def test_restore_rejects_lost_or_duplicated_placeholder_token() -> None:
    protected = PlaceholderProtector().protect("Hello {name}")
    token = protected.replacements[0][0]

    with pytest.raises(PlaceholderMismatchError, match="occurs 0 times"):
        protected.restore("Привет")
    with pytest.raises(PlaceholderMismatchError, match="occurs 2 times"):
        protected.restore(f"Привет {token} {token}")
