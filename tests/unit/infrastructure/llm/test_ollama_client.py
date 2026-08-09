import json
from typing import Any

import pytest

from locaforge.application.dto.review import ReviewRequest, ReviewRequestItem
from locaforge.application.dto.translation import TranslationRequest, TranslationRequestItem
from locaforge.application.errors import InvalidModelResponseError
from locaforge.infrastructure.llm.ollama_client import OllamaClient


class FakeHttpResponse:
    def __init__(self, body: dict[str, object]) -> None:
        self._body = json.dumps(body).encode("utf-8")

    def __enter__(self) -> "FakeHttpResponse":
        return self

    def __exit__(self, *arguments: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def make_request() -> TranslationRequest:
    return TranslationRequest(
        model="qwen3",
        source_language="en",
        target_language="ru",
        entries=(TranslationRequestItem("entry-1", "Hello"),),
        prompt="Translate",
        timeout_seconds=5.0,
    )


def make_review_request() -> ReviewRequest:
    return ReviewRequest(
        "qwen3",
        "zh",
        "en",
        (ReviewRequestItem("entry-1", "保存", "Preserve"),),
        5.0,
    )


def test_translate_sends_ollama_request_and_parses_json(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_urlopen(request: Any, timeout: float) -> FakeHttpResponse:
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeHttpResponse(
            {"response": '{"translations":[{"entry_id":"entry-1","translation":"Привет"}]}' }
        )

    monkeypatch.setattr("locaforge.infrastructure.llm.ollama_client.urlopen", fake_urlopen)

    response = OllamaClient().translate(make_request())

    assert response.results[0].translation == "Привет"
    assert captured == {
        "url": "http://127.0.0.1:11434/api/generate",
        "payload": {"model": "qwen3", "prompt": "Translate", "stream": False, "format": "json"},
        "timeout": 5.0,
    }


def test_translate_rejects_non_json_model_output(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: Any, timeout: float) -> FakeHttpResponse:
        return FakeHttpResponse({"response": "not JSON"})

    monkeypatch.setattr("locaforge.infrastructure.llm.ollama_client.urlopen", fake_urlopen)

    with pytest.raises(InvalidModelResponseError, match="non-JSON"):
        OllamaClient().translate(make_request())


def test_review_parses_model_findings(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: Any, timeout: float) -> FakeHttpResponse:
        return FakeHttpResponse(
            {
                "response": '{"reviews":[{"entry_id":"entry-1",'
                '"issue":"Wrong meaning","suggested_translation":"Keep"}]}'
            }
        )

    monkeypatch.setattr("locaforge.infrastructure.llm.ollama_client.urlopen", fake_urlopen)

    response = OllamaClient().review(make_review_request())

    assert response.results[0].issue == "Wrong meaning"
    assert response.results[0].suggested_translation == "Keep"


def test_list_models_reads_and_sorts_ollama_tags(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: Any, timeout: float) -> FakeHttpResponse:
        return FakeHttpResponse(
            {"models": [{"name": "qwen3:8b"}, {"name": "gemma3:12b"}]}
        )

    monkeypatch.setattr("locaforge.infrastructure.llm.ollama_client.urlopen", fake_urlopen)

    assert OllamaClient().list_models() == ("gemma3:12b", "qwen3:8b")


def test_pull_model_uses_non_streaming_api(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_urlopen(request: Any, timeout: float) -> FakeHttpResponse:
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeHttpResponse({"status": "success"})

    monkeypatch.setattr("locaforge.infrastructure.llm.ollama_client.urlopen", fake_urlopen)

    OllamaClient().pull_model("qwen3:8b")

    assert captured == {
        "url": "http://127.0.0.1:11434/api/pull",
        "payload": {"model": "qwen3:8b", "stream": False},
        "timeout": 3600.0,
    }
