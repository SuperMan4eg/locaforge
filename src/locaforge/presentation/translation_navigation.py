"""Small helpers for navigating the filtered translation table."""

from collections.abc import Collection, Sequence


def adjacent_row_index(current_row: int, row_count: int, offset: int) -> int | None:
    if row_count < 1 or offset == 0:
        return None
    target = current_row + offset
    if target < 0 or target >= row_count:
        return None
    return target


def next_matching_entry_id(
    entry_ids: Sequence[str],
    current_entry_id: str | None,
    matching_entry_ids: Collection[str],
    offset: int,
) -> str | None:
    if offset == 0:
        return None
    matching_ids = [entry_id for entry_id in entry_ids if entry_id in matching_entry_ids]
    if not matching_ids:
        return None
    if current_entry_id not in matching_ids:
        return matching_ids[0] if offset > 0 else matching_ids[-1]
    current_index = matching_ids.index(current_entry_id)
    return matching_ids[(current_index + offset) % len(matching_ids)]
