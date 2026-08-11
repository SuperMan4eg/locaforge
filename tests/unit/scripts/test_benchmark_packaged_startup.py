from pathlib import Path

from scripts.benchmark_packaged_startup import _directory_size, _percentile


def test_packaged_percentile_uses_nearest_rank() -> None:
    assert _percentile([1.0, 5.0, 2.0, 4.0, 3.0], 0.95) == 5.0


def test_directory_size_sums_nested_files(tmp_path: Path) -> None:
    (tmp_path / "root.bin").write_bytes(b"123")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "child.bin").write_bytes(b"12345")

    assert _directory_size(tmp_path) == 8
