import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from locaforge.presentation.language_registry import canonical_bcp47
from locaforge.presentation.searchable_language_combo_box import SearchableLanguageComboBox


def test_language_codes_are_canonicalized_and_displayed() -> None:
    application = QApplication.instance() or QApplication([])
    language = SearchableLanguageComboBox("PT_br")

    assert application is not None
    assert language.language_code() == "pt-BR"
    assert language.text() == "Português (Brasil) — pt-BR"
    assert canonical_bcp47("zh_cn") == "zh-CN"


def test_language_picker_filters_by_name_and_code() -> None:
    application = QApplication.instance() or QApplication([])
    language = SearchableLanguageComboBox("en")

    language.lineEdit().textEdited.emit("рус")
    assert language.model().rowCount() == 1
    assert language.model().index(0, 0).data() == "Русский — ru"

    language.lineEdit().textEdited.emit("zh-CN")
    assert language.model().rowCount() == 1
    assert language.model().index(0, 0).data() == "中文 (中国) — zh-CN"
    assert language.language_code() is None
    assert application is not None


def test_unknown_legacy_language_is_kept_as_a_temporary_choice() -> None:
    application = QApplication.instance() or QApplication([])
    language = SearchableLanguageComboBox("x-klingon")

    assert application is not None
    assert language.language_code() == "x-klingon"
    assert language.text() == "Unknown language (temporary) — x-klingon"


def test_arbitrary_typed_value_cannot_be_saved_as_a_language() -> None:
    application = QApplication.instance() or QApplication([])
    language = SearchableLanguageComboBox("en")

    language.lineEdit().setText("not a language")
    language.lineEdit().textEdited.emit("not a language")

    assert application is not None
    assert language.language_code() is None
    assert language.findData("not a language", language.code_role) == -1
