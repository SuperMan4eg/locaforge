from locaforge.presentation.translation_navigation import (
    adjacent_row_index,
    next_matching_entry_id,
)


def test_finds_adjacent_row_within_bounds() -> None:
    assert adjacent_row_index(4, 10, 1) == 5
    assert adjacent_row_index(4, 10, -1) == 3


def test_returns_none_for_empty_or_out_of_bounds_navigation() -> None:
    assert adjacent_row_index(0, 0, 1) is None
    assert adjacent_row_index(0, 3, -1) is None
    assert adjacent_row_index(2, 3, 1) is None
    assert adjacent_row_index(1, 3, 0) is None


def test_cycles_through_matching_entry_ids() -> None:
    entry_ids = ("one", "two", "three", "four")
    matching_ids = {"two", "four"}

    assert next_matching_entry_id(entry_ids, "two", matching_ids, 1) == "four"
    assert next_matching_entry_id(entry_ids, "four", matching_ids, 1) == "two"
    assert next_matching_entry_id(entry_ids, "two", matching_ids, -1) == "four"


def test_selects_edge_match_when_current_entry_has_no_issue() -> None:
    entry_ids = ("one", "two", "three")

    assert next_matching_entry_id(entry_ids, "one", {"two", "three"}, 1) == "two"
    assert next_matching_entry_id(entry_ids, "one", {"two", "three"}, -1) == "three"
    assert next_matching_entry_id(entry_ids, "one", set(), 1) is None


def test_cycles_through_actionable_entry_ids() -> None:
    entry_ids = ("translated", "untranslated", "needs-review", "error", "approved")
    actionable_ids = {"untranslated", "needs-review", "error"}

    assert next_matching_entry_id(entry_ids, "translated", actionable_ids, 1) == "untranslated"
    assert next_matching_entry_id(entry_ids, "error", actionable_ids, 1) == "untranslated"
