import json
from typing import Any

import pytest

from locaforge.application.dto.project_description import ProjectDescriptionRequest
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
            {
                "response": '{"translations":[{"entry_id":"entry-1","translation":"Привет"}]}',
                "total_duration": 2_000_000_000,
                "load_duration": 100_000_000,
                "prompt_eval_count": 40,
                "prompt_eval_duration": 400_000_000,
                "eval_count": 20,
                "eval_duration": 1_000_000_000,
            }
        )

    monkeypatch.setattr("locaforge.infrastructure.llm.ollama_client.urlopen", fake_urlopen)

    response = OllamaClient().translate(make_request())

    assert response.results[0].translation == "Привет"
    assert captured == {
        "url": "http://127.0.0.1:11434/api/generate",
        "payload": {
            "model": "qwen3",
            "prompt": "Translate",
            "stream": False,
            "format": "json",
            "think": False,
            "keep_alive": 300,
        },
        "timeout": 5.0,
    }
    assert response.usage.total_duration_ns == 2_000_000_000
    assert response.usage.generation_tokens_per_second == 20.0


def test_client_aggregates_privacy_safe_usage_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(request: Any, timeout: float) -> FakeHttpResponse:
        return FakeHttpResponse(
            {
                "response": '{"translations":[]}',
                "total_duration": 10,
                "load_duration": 2,
                "prompt_eval_count": 3,
                "prompt_eval_duration": 4,
                "eval_count": 5,
                "eval_duration": 6,
            }
        )

    monkeypatch.setattr("locaforge.infrastructure.llm.ollama_client.urlopen", fake_urlopen)
    client = OllamaClient()

    client.translate(make_request())
    client.translate(make_request())

    snapshot = client.performance_snapshot()
    assert snapshot.request_count == 2
    assert snapshot.total_duration_ns == 20
    assert snapshot.load_duration_ns == 4
    assert snapshot.prompt_eval_count == 6
    assert snapshot.eval_count == 10
    assert snapshot.eval_duration_ns == 12


def test_translate_rejects_non_json_model_output(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: Any, timeout: float) -> FakeHttpResponse:
        return FakeHttpResponse({"response": "not JSON"})

    monkeypatch.setattr("locaforge.infrastructure.llm.ollama_client.urlopen", fake_urlopen)

    with pytest.raises(InvalidModelResponseError, match="non-JSON"):
        OllamaClient().translate(make_request())


def test_translate_sends_selected_reasoning_level(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_urlopen(request: Any, timeout: float) -> FakeHttpResponse:
        captured.update(json.loads(request.data.decode("utf-8")))
        return FakeHttpResponse({"response": '{"translations":[]}'})

    monkeypatch.setattr("locaforge.infrastructure.llm.ollama_client.urlopen", fake_urlopen)
    request = make_request()
    OllamaClient().translate(
        TranslationRequest(
            request.model,
            request.source_language,
            request.target_language,
            request.entries,
            request.prompt,
            request.timeout_seconds,
            "medium",
        )
    )

    assert captured["think"] == "medium"


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


def test_describe_project_parses_structured_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(request: Any, timeout: float) -> FakeHttpResponse:
        return FakeHttpResponse(
            {
                "response": json.dumps(
                    {
                        "description": "A space exploration game.",
                        "project_type": "Game",
                        "domain": "Science fiction",
                        "tone": "Cinematic",
                    }
                )
            }
        )

    monkeypatch.setattr("locaforge.infrastructure.llm.ollama_client.urlopen", fake_urlopen)

    response = OllamaClient().describe_project(
        ProjectDescriptionRequest("Nebula", "qwen3", 12.0)
    )

    assert response.profile.description == "A space exploration game."
    assert response.profile.project_type == "Game"
    assert response.profile.domain == "Science fiction"


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
