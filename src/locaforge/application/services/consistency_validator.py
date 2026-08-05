"""Project-wide consistency checks for repeated source strings."""

from collections import defaultdict
from collections.abc import Iterable

from locaforge.application.dto.validation import ValidationCode, ValidationIssue
from locaforge.domain.entry import TranslationEntry


class ConsistencyValidator:
    """Finds different translations for the same source and context."""

    def validate(
        self, entries: Iterable[TranslationEntry]
    ) -> dict[str, tuple[ValidationIssue, ...]]:
        groups: dict[tuple[str, str | None], list[TranslationEntry]] = defaultdict(
            list
        )
        for entry in entries:
            if entry.translation is not None and entry.translation.strip():
                groups[(entry.source.strip(), entry.context)].append(entry)

        issues_by_entry: dict[str, tuple[ValidationIssue, ...]] = {}
        for grouped_entries in groups.values():
            translations = {
                entry.translation.strip()
                for entry in grouped_entries
                if entry.translation is not None
            }
            if len(translations) < 2:
                continue
            variants = ", ".join(
                f"«{translation}»" for translation in sorted(translations)[:3]
            )
            if len(translations) > 3:
                variants += ", …"
            issue = ValidationIssue(
                ValidationCode.INCONSISTENT_TRANSLATION,
                f"Same source has {len(translations)} translations: {variants}",
            )
            for entry in grouped_entries:
                issues_by_entry[entry.id] = (issue,)
        return issues_by_entry
