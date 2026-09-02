"""Free-slot arithmetic - the foundation of the scheduler."""
from __future__ import annotations

from datetime import date, time

import pytest

from app.utils.timeutils import (Interval, date_range, intersect_all,
                                 merge_intervals, parse_date, parse_time,
                                 slice_into_slots, subtract_intervals)
from tests.conftest import iv


def test_free_slots_match_the_specification_example():
    """09:00-17:00 minus 10:00-11:00 and 13:00-14:00."""
    free = subtract_intervals([iv("09:00", "17:00")],
                              [iv("10:00", "11:00"), iv("13:00", "14:00")])
    assert [str(i) for i in free] == ["09:00-10:00", "11:00-13:00", "14:00-17:00"]


def test_subtract_handles_overlapping_and_touching_blocks():
    free = subtract_intervals([iv("09:00", "12:00")],
                              [iv("09:00", "10:00"), iv("09:30", "11:00"),
                               iv("11:00", "12:00")])
    assert free == []


def test_subtract_block_outside_window_is_ignored():
    free = subtract_intervals([iv("09:00", "10:00")], [iv("14:00", "15:00")])
    assert [str(i) for i in free] == ["09:00-10:00"]


def test_merge_intervals_unions_overlaps():
    merged = merge_intervals([iv("09:00", "10:00"), iv("09:30", "11:00"),
                              iv("12:00", "13:00")])
    assert [str(i) for i in merged] == ["09:00-11:00", "12:00-13:00"]


def test_intersect_all_finds_common_panel_time():
    common = intersect_all([[iv("09:00", "12:00")], [iv("10:00", "13:00")],
                            [iv("09:30", "11:30")]])
    assert [str(i) for i in common] == ["10:00-11:30"]


def test_intersect_all_returns_empty_when_no_overlap():
    assert intersect_all([[iv("09:00", "10:00")], [iv("11:00", "12:00")]]) == []


def test_slice_into_slots_respects_duration_and_granularity():
    slots = slice_into_slots(iv("09:00", "10:00"), duration=30, granularity=30)
    assert [str(s) for s in slots] == ["09:00-09:30", "09:30-10:00"]


def test_slice_into_slots_keeps_room_for_the_break():
    slots = slice_into_slots(iv("09:00", "10:00"), duration=30, granularity=15,
                             buffer_after=10)
    # 09:15-09:45 would need until 09:55 which still fits; 09:30-10:00 ends exactly
    # at the boundary so it is allowed too.
    assert [str(s) for s in slots] == ["09:00-09:30", "09:15-09:45", "09:30-10:00"]


def test_slice_into_slots_rejects_too_short_interval():
    assert slice_into_slots(iv("09:00", "09:20"), duration=30, granularity=15) == []


@pytest.mark.parametrize("raw,expected", [
    ("09:00", time(9, 0)),
    ("9:00 AM", time(9, 0)),
    ("02:30 PM", time(14, 30)),
    ("14:30:00", time(14, 30)),
    (0.375, time(9, 0)),
    (930, time(9, 30)),
    ("", None),
    ("not a time", None),
])
def test_parse_time_accepts_spreadsheet_formats(raw, expected):
    assert parse_time(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("2026-03-02", date(2026, 3, 2)),
    ("02-03-2026", date(2026, 3, 2)),
    ("02/03/2026", date(2026, 3, 2)),
    ("nan", None),
])
def test_parse_date_accepts_spreadsheet_formats(raw, expected):
    assert parse_date(raw) == expected


def test_date_range_can_skip_weekends():
    days = date_range(date(2026, 3, 6), date(2026, 3, 10), include_weekends=False)
    assert days == [date(2026, 3, 6), date(2026, 3, 9), date(2026, 3, 10)]


def test_interval_rejects_reversed_bounds():
    with pytest.raises(ValueError):
        Interval(600, 540)
