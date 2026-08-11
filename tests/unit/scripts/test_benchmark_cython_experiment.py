from scripts.benchmark_cython_experiment import _summary


def test_cython_summary_reports_measured_range() -> None:
    assert _summary([3.0, 1.0, 2.0]) == {
        "median_ms": 2.0,
        "minimum_ms": 1.0,
        "maximum_ms": 3.0,
    }
