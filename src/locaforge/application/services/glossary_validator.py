"""Glossary terminology validation."""

from __future__ import annotations

import re
from collections.abc import Sequence
from functools import lru_cache

from locaforge.application.dto.validation import ValidationCode, ValidationIssue
from locaforge.domain.glossary import GlossaryTerm


class GlossaryValidator:
    """Checks that relevant required glossary targets are used."""

    def validate(
        self,
        source: str,
        translation: str,
        terms: Sequence[GlossaryTerm],
    ) -> tuple[ValidationIssue, ...]:
        issues: list[ValidationIssue] = []
        for term in terms:
            source_flags = 0 if term.case_sensitive else re.IGNORECASE
            if not self._contains(source, term.source, source_flags):
                continue
            if self._contains(translation, term.target, re.IGNORECASE):
                continue
            issues.append(
                ValidationIssue(
                    ValidationCode.GLOSSARY_MISMATCH,
                    f"Required glossary translation {term.target!r} "
                    f"for source term {term.source!r} is missing",
                )
            )
        return tuple(issues)

    @staticmethod
    def _contains(text: str, term: str, flags: int) -> bool:
        return GlossaryValidator._pattern(term, flags).search(text) is not None

    @staticmethod
    @lru_cache(maxsize=2048)
    def _pattern(term: str, flags: int) -> re.Pattern[str]:
        return re.compile(rf"(?<!\w){re.escape(term)}(?!\w)", flags)
