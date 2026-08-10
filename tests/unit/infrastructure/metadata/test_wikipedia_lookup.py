import json
from typing import Any

import pytest

from locaforge.infrastructure.metadata.wikipedia_lookup import (
    WikipediaProjectMetadataLookup,
)


class FakeResponse:
    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *arguments: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(
            {
                "query": {
                    "search": [
                        {
                            "title": "Nebula",
                            "snippet": "A <span>science fiction</span> project &amp; game.",
                        }
                    ]
                }
            }
        ).encode()


def test_wikipedia_lookup_sends_only_name_and_strips_markup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_urlopen(request: Any, timeout: float) -> FakeResponse:
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(
        "locaforge.infrastructure.metadata.wikipedia_lookup.urlopen", fake_urlopen
    )

    result = WikipediaProjectMetadataLookup().lookup("Nebula")

    assert "srsearch=Nebula" in captured["url"]
    assert captured["timeout"] == 10.0
    assert result == "Nebula: A science fiction project & game."
