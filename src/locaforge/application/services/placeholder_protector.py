"""Protection and validation of placeholder-bearing translation strings."""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import uuid4

from locaforge.application.errors import PlaceholderMismatchError

_PLACEHOLDER_PATTERN = re.compile(
    r"%(?:\([^)]+\))?[#0 +\-]?(?:\d+|\*)?(?:\.\d+)?[diouxXeEfFgGcrs]"
    r"|\{[^{}]+\}"
    r"|\\(?:[nrt\\\"'])"
    r"|</?[A-Za-z][^>]*>"
)


@dataclass(frozen=True, slots=True)
class ProtectedText:
    """A source string with placeholders replaced by model-safe tokens."""

    source: str
    protected: str
    replacements: tuple[tuple[str, str], ...]

    def restore(self, translation: str) -> str:
        """Verify every protected token then restore its exact source placeholder."""
        restored = translation
        for token, placeholder in self.replacements:
            occurrences = restored.count(token)
            if occurrences != 1:
                raise PlaceholderMismatchError(
                    f"Placeholder token {token!r} occurs {occurrences} times in model output"
                )
            restored = restored.replace(token, placeholder)
        return restored


class PlaceholderProtector:
    """Protects placeholders supported by the MVP translation pipeline."""

    def protect(self, source: str) -> ProtectedText:
        matches = list(_PLACEHOLDER_PATTERN.finditer(source))
        if not matches:
            return ProtectedText(source=source, protected=source, replacements=())

        token_prefix = f"__LF_PH_{uuid4().hex}_"
        replacements: list[tuple[str, str]] = []
        pieces: list[str] = []
        cursor = 0
        for index, match in enumerate(matches):
            token = f"{token_prefix}{index}__"
            pieces.extend((source[cursor : match.start()], token))
            replacements.append((token, match.group(0)))
            cursor = match.end()
        pieces.append(source[cursor:])
        return ProtectedText(
            source=source,
            protected="".join(pieces),
            replacements=tuple(replacements),
        )

    def extract(self, text: str) -> tuple[str, ...]:
        return tuple(match.group(0) for match in _PLACEHOLDER_PATTERN.finditer(text))
