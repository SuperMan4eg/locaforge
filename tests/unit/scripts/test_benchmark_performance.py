from scripts.benchmark_performance import (
    BenchmarkReport,
    _valid_translation_count,
    render_markdown,
    runtime_metadata,
    summarize,
)


def test_summarize_uses_nearest_rank_for_p95() -> None:
    result = summarize("example", 10, [1.0, 5.0, 2.0, 4.0, 3.0])

    assert result.median_ms == 3.0
    assert result.p95_ms == 5.0
    assert result.minimum_ms == 1.0
    assert result.maximum_ms == 5.0


def test_render_markdown_contains_results_and_environment() -> None:
    result = summarize("lookup", 1_000, [2.5])
    report = BenchmarkReport(
        schema_version=1,
        generated_at="2026-08-11T00:00:00+00:00",
        environment={"python": "3.14.6"},
        configuration={},
        results=(result,),
    )

    rendered = render_markdown(report)

    assert "| `lookup` | 1000 | 2.500 |" in rendered
    assert "- python: `3.14.6`" in rendered


def test_benchmark_report_environment_accepts_runtime_mode_metadata() -> None:
    report = BenchmarkReport(
        schema_version=1,
        generated_at="2026-08-11T00:00:00+00:00",
        environment={
            "python_jit_available": "True",
            "python_jit_enabled": "False",
            "python_gil_enabled": "True",
        },
        configuration={},
        results=(summarize("lookup", 1, [1.0]),),
    )

    rendered = render_markdown(report)

    assert "- python_jit_enabled: `False`" in rendered


def test_runtime_metadata_has_cross_version_fallbacks() -> None:
    metadata = runtime_metadata()

    assert set(metadata) == {
        "python_jit_available",
        "python_jit_enabled",
        "python_gil_enabled",
        "python_compiled",
    }
    assert set(metadata.values()) <= {"True", "False"}


def test_ollama_result_count_requires_structured_unique_translations() -> None:
    response = {
        "response": (
            '{"translations":['
            '{"entry_id":"a","translation":"A"},'
            '{"entry_id":"a","translation":"duplicate"},'
            '{"entry_id":"b","translation":"B"},'
            '{"entry_id":"c","translation":null}'
            "]}"
        )
    }

    assert _valid_translation_count(response) == 2
    assert _valid_translation_count({"response": "not json"}) == 0
