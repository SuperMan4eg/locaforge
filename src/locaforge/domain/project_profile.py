"""Descriptive project context used by people and translation models."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Self


@dataclass(slots=True)
class ProjectProfile:
    """User-owned metadata describing the product being localized."""

    description: str = ""
    project_type: str = ""
    domain: str = ""
    target_audience: str = ""
    tone: str = ""
    platform: str = ""
    translation_instructions: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, values: object) -> Self:
        if not isinstance(values, dict):
            return cls()
        fields = cls.__dataclass_fields__
        return cls(
            **{
                name: value
                for name, value in values.items()
                if name in fields and isinstance(value, str)
            }
        )
