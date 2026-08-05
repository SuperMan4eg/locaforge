"""CSV format contract for glossary term interchange."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from locaforge.domain.glossary import GlossaryTerm


class GlossaryCsvFormat(Protocol):
    """Imports and exports glossary terms in a portable CSV format."""

    def import_file(
        self,
        path: Path,
        source_language: str,
        target_language: str,
    ) -> tuple[GlossaryTerm, ...]: ...

    def export_file(self, terms: tuple[GlossaryTerm, ...], path: Path) -> None: ...
