"""Interval arithmetic used by free-slot computation and conflict detection.

Times are handled as *minutes since midnight* internally which keeps the
algorithms integer-only and free of timezone surprises.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Iterable, Sequence

_TIME_PATTERNS = (
    "%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M%p", "%I %p", "%I:%M:%S %p",
    "%H.%M", "%H%M",
)
_DATE_PATTERNS = (
    "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d",
    "%d-%b-%Y", "%d %b %Y", "%b %d %Y", "%d.%m.%Y",
)


def to_minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def from_minutes(value: int) -> time:
    value = max(0, min(value, 24 * 60 - 1))
    return time(hour=value // 60, minute=value % 60)


def parse_time(value: object) -> time | None:
    """Parse the many shapes a spreadsheet cell can hold ('9:00', '09:00 AM')."""
    if value is None:
        return None
    if isinstance(value, time):
        return value.replace(second=0, microsecond=0)
    if isinstance(value, datetime):
        return value.time().replace(second=0, microsecond=0)
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        # Excel serial fraction of a day (0.375 == 09:00)
        if 0 <= float(value) < 1:
            return from_minutes(int(round(float(value) * 24 * 60)))
        as_int = int(value)
        if 0 <= as_int <= 2359:
            return from_minutes((as_int // 100) * 60 + as_int % 100)
        return None
    text = str(value).strip().upper().replace(".", ":")
    if not text or text in {"NAN", "NAT", "NONE", "NULL", "-"}:
        return None
    text = re.sub(r"\s+", " ", text)
    for pattern in _TIME_PATTERNS:
        try:
            return datetime.strptime(text, pattern.upper()).time().replace(
                second=0, microsecond=0)
        except ValueError:
            continue
    match = re.match(r"^(\d{1,2}):(\d{2})", text)
    if match:
        hour, minute = int(match.group(1)), int(match.group(2))
        if 0 <= hour < 24 and 0 <= minute < 60:
            return time(hour, minute)
    return None


def parse_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text or text.lower() in {"nan", "nat", "none", "null", "-"}:
        return None
    if " " in text and ":" in text:
        text = text.split(" ")[0]
    for pattern in _DATE_PATTERNS:
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        return None


@dataclass(frozen=True, slots=True)
class Interval:
    """A half-open [start, end) range of minutes within a single day."""

    start: int
    end: int

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError(f"Invalid interval: {self.start} > {self.end}")

    @classmethod
    def from_times(cls, start: time, end: time) -> "Interval":
        return cls(to_minutes(start), to_minutes(end))

    @property
    def duration(self) -> int:
        return self.end - self.start

    @property
    def start_time(self) -> time:
        return from_minutes(self.start)

    @property
    def end_time(self) -> time:
        return from_minutes(self.end)

    def overlaps(self, other: "Interval") -> bool:
        return self.start < other.end and other.start < self.end

    def contains(self, other: "Interval") -> bool:
        return self.start <= other.start and other.end <= self.end

    def __str__(self) -> str:  # pragma: no cover - display helper
        return f"{self.start_time:%H:%M}-{self.end_time:%H:%M}"


def merge_intervals(intervals: Iterable[Interval]) -> list[Interval]:
    """Union of possibly overlapping intervals, sorted by start."""
    ordered = sorted((i for i in intervals if i.duration > 0), key=lambda i: (i.start, i.end))
    merged: list[Interval] = []
    for interval in ordered:
        if merged and interval.start <= merged[-1].end:
            last = merged.pop()
            merged.append(Interval(last.start, max(last.end, interval.end)))
        else:
            merged.append(interval)
    return merged


def subtract_intervals(base: Sequence[Interval],
                       blocks: Sequence[Interval]) -> list[Interval]:
    """`base` minus `blocks` -> the remaining free intervals.

    This is the core of faculty free-slot calculation:
        [09:00-17:00] - [10:00-11:00, 13:00-14:00]
          => [09:00-10:00, 11:00-13:00, 14:00-17:00]
    """
    blocked = merge_intervals(blocks)
    result: list[Interval] = []
    for window in merge_intervals(base):
        cursor = window.start
        for block in blocked:
            if block.end <= cursor or block.start >= window.end:
                continue
            if block.start > cursor:
                result.append(Interval(cursor, min(block.start, window.end)))
            cursor = max(cursor, block.end)
            if cursor >= window.end:
                break
        if cursor < window.end:
            result.append(Interval(cursor, window.end))
    return [i for i in result if i.duration > 0]


def intersect_intervals(a: Sequence[Interval], b: Sequence[Interval]) -> list[Interval]:
    """Intersection of two interval sets (used to find common panel free time)."""
    left, right = merge_intervals(a), merge_intervals(b)
    result: list[Interval] = []
    i = j = 0
    while i < len(left) and j < len(right):
        start = max(left[i].start, right[j].start)
        end = min(left[i].end, right[j].end)
        if end > start:
            result.append(Interval(start, end))
        if left[i].end < right[j].end:
            i += 1
        else:
            j += 1
    return result


def intersect_all(sets: Sequence[Sequence[Interval]]) -> list[Interval]:
    if not sets:
        return []
    current = merge_intervals(sets[0])
    for other in sets[1:]:
        current = intersect_intervals(current, other)
        if not current:
            break
    return current


def slice_into_slots(interval: Interval, duration: int, granularity: int,
                     *, buffer_after: int = 0) -> list[Interval]:
    """Candidate start positions inside a free interval.

    `duration` is the interview length; `buffer_after` (the break) must also fit
    inside the interval unless the interview ends exactly at the interval end.
    """
    if duration <= 0 or interval.duration < duration:
        return []
    granularity = max(1, granularity)
    slots: list[Interval] = []
    start = interval.start
    while start + duration <= interval.end:
        end = start + duration
        if end + buffer_after <= interval.end or end == interval.end:
            slots.append(Interval(start, end))
        start += granularity
    return slots


def date_range(start: date, end: date, *, include_weekends: bool = True) -> list[date]:
    if end < start:
        return []
    days: list[date] = []
    current = start
    while current <= end:
        if include_weekends or current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def format_interval(interval: Interval) -> str:
    return f"{interval.start_time.strftime('%H:%M')}-{interval.end_time.strftime('%H:%M')}"
