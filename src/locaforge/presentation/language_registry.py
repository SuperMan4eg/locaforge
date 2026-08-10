"""Shared language catalogue and BCP-47 code normalization."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Language:
    """A language that can be selected in project and application settings."""

    name: str
    code: str

    @property
    def label(self) -> str:
        return f"{self.name} — {self.code}"


LANGUAGES: tuple[Language, ...] = (
    Language("Русский", "ru"),
    Language("English", "en"),
    Language("English (United States)", "en-US"),
    Language("English (United Kingdom)", "en-GB"),
    Language("العربية", "ar"),
    Language("Български", "bg"),
    Language("বাংলা", "bn"),
    Language("Català", "ca"),
    Language("Čeština", "cs"),
    Language("Dansk", "da"),
    Language("Deutsch", "de"),
    Language("Ελληνικά", "el"),
    Language("Українська", "uk"),
    Language("Français", "fr"),
    Language("Español", "es"),
    Language("Español (Latinoamérica)", "es-419"),
    Language("Eesti", "et"),
    Language("فارسی", "fa"),
    Language("Suomi", "fi"),
    Language("עברית", "he"),
    Language("हिन्दी", "hi"),
    Language("Hrvatski", "hr"),
    Language("Magyar", "hu"),
    Language("Bahasa Indonesia", "id"),
    Language("Italiano", "it"),
    Language("Қазақша", "kk"),
    Language("Português", "pt"),
    Language("Português (Portugal)", "pt-PT"),
    Language("Português (Brasil)", "pt-BR"),
    Language("中文", "zh"),
    Language("中文 (中国)", "zh-CN"),
    Language("中文 (台灣)", "zh-TW"),
    Language("日本語", "ja"),
    Language("한국어", "ko"),
    Language("Lietuvių", "lt"),
    Language("Latviešu", "lv"),
    Language("Bahasa Melayu", "ms"),
    Language("Nederlands", "nl"),
    Language("Norsk Bokmål", "nb"),
    Language("Polski", "pl"),
    Language("Română", "ro"),
    Language("Slovenčina", "sk"),
    Language("Slovenščina", "sl"),
    Language("Српски", "sr"),
    Language("Српски (ћирилица)", "sr-Cyrl"),
    Language("Srpski (latinica)", "sr-Latn"),
    Language("Svenska", "sv"),
    Language("ไทย", "th"),
    Language("Türkçe", "tr"),
    Language("Tiếng Việt", "vi"),
)

_BCP47_PATTERN = re.compile(r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$")


def canonical_bcp47(code: str) -> str | None:
    """Return conventional BCP-47 casing for a syntactically valid tag."""

    value = code.strip().replace("_", "-")
    if not _BCP47_PATTERN.fullmatch(value):
        return None
    subtags = value.split("-")
    canonical = [subtags[0].lower()]
    for subtag in subtags[1:]:
        if len(subtag) == 4 and subtag.isalpha():
            canonical.append(subtag.title())
        elif (len(subtag) == 2 and subtag.isalpha()) or (
            len(subtag) == 3 and subtag.isdigit()
        ):
            canonical.append(subtag.upper())
        else:
            canonical.append(subtag.lower())
    return "-".join(canonical)


def language_for_code(code: str) -> Language | None:
    """Find a catalogued language by code, accepting non-canonical input."""

    canonical = canonical_bcp47(code)
    if canonical is None:
        return None
    return next((language for language in LANGUAGES if language.code == canonical), None)
