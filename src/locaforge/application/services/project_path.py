"""Cross-platform validation for paths stored inside a project."""

from pathlib import PurePosixPath, PureWindowsPath


def is_safe_project_path(value: str) -> bool:
    """Return whether *value* is a non-empty relative path on every supported OS."""
    if not value:
        return False
    posix_path = PurePosixPath(value)
    windows_path = PureWindowsPath(value)
    return (
        not posix_path.is_absolute()
        and not windows_path.drive
        and ".." not in posix_path.parts
        and ".." not in windows_path.parts
    )
