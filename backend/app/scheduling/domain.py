"""Domain generation: every legal candidate x panel x time-slot combination.

This is step 5-7 of the documented algorithm - build the combinations, drop the
ones violating hard constraints, and pre-score the survivors so the solver can
explore the most promising placements first.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date

from app.scheduling.constraints import evaluate_static
from app.scheduling.types import (CandidateSpec, PanelSpec, SchedulingContext,
                                  SlotOption, UnscheduledCandidate)
from app.utils.timeutils import (Interval, merge_intervals, slice_into_slots,
                                 to_minutes)


def _day_window(ctx: SchedulingContext) -> Interval:
    start = to_minutes(ctx.options.day_start) if ctx.options.day_start else 0
    end = to_minutes(ctx.options.day_end) if ctx.options.day_end else 24 * 60 - 1
    return Interval(start, max(start, end))


def _panel_candidate_slots(ctx: SchedulingContext, panel: PanelSpec, day: date,
                           window: Interval) -> list[Interval]:
    """Distinct start positions worth trying for a panel on a day.

    Built from the union of member free time (a slot only needs *some* members),
    clipped to the working window and sliced at the configured granularity.
    """
    windows: list[Interval] = []
    for fid in panel.member_ids:
        spec = ctx.faculty.get(fid)
        if spec is None:
            continue
        for free in spec.free_slots.get(day, ()):
            start, end = max(free.start, window.start), min(free.end, window.end)
            if end - start >= ctx.options.duration_minutes:
                windows.append(Interval(start, end))
    slots: list[Interval] = []
    seen: set[tuple[int, int]] = set()
    for merged in merge_intervals(windows):
        for slot in slice_into_slots(merged, ctx.options.duration_minutes,
                                     ctx.options.granularity_minutes,
                                     buffer_after=0):
            key = (slot.start, slot.end)
            if key not in seen:
                seen.add(key)
                slots.append(slot)
    return slots


def generate_options(
    ctx: SchedulingContext,
) -> tuple[dict[int, list[SlotOption]], dict[int, UnscheduledCandidate]]:
    """Return feasible options per candidate plus reasons for empty domains."""
    window = _day_window(ctx)
    options: dict[int, list[SlotOption]] = defaultdict(list)
    rejections: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    # Slot grids are identical for every candidate, so compute them once.
    panel_slots: dict[tuple[int, date], list[Interval]] = {}
    for panel in ctx.panels:
        for day in ctx.options.dates:
            panel_slots[(panel.id, day)] = _panel_candidate_slots(ctx, panel, day, window)

    for candidate in ctx.candidates:
        for panel in ctx.panels:
            required = max(1, panel.minimum_panel_size)
            for day in ctx.options.dates:
                if day in candidate.blocked_dates:
                    rejections[candidate.id]["Candidate blocked this date"] += 1
                    continue
                for slot in panel_slots[(panel.id, day)]:
                    if not candidate.is_available(day, slot):
                        rejections[candidate.id]["Outside candidate availability"] += 1
                        continue
                    eligible = [fid for fid in panel.member_ids
                                if ctx.faculty.get(fid)
                                and ctx.faculty[fid].is_free(day, slot)]
                    if len(eligible) < required:
                        rejections[candidate.id][
                            f"Panel {panel.code} had fewer than {required} free faculty"] += 1
                        continue
                    if not panel.mandatory_ids.issubset(set(eligible)):
                        rejections[candidate.id][
                            f"Mandatory member of panel {panel.code} unavailable"] += 1
                        continue
                    provisional = _provisional_members(panel, eligible, required)
                    feasible, outcomes, reason = evaluate_static(
                        ctx, candidate, panel, day, slot, provisional)
                    if not feasible:
                        rejections[candidate.id][reason or "Hard constraint violated"] += 1
                        continue
                    options[candidate.id].append(SlotOption(
                        candidate_id=candidate.id, panel_id=panel.id, day=day, slot=slot,
                        eligible_faculty_ids=eligible, required_size=required,
                        score=sum(o.score for o in outcomes), outcomes=outcomes,
                    ))

    for candidate in ctx.candidates:
        bucket = options.get(candidate.id)
        if bucket:
            # Best first; ties broken by earliest date/time for a stable schedule.
            bucket.sort(key=lambda o: (-o.score, o.day, o.slot.start, o.panel_id))
            del bucket[ctx.options.max_options_per_candidate:]

    unscheduled: dict[int, UnscheduledCandidate] = {}
    for candidate in ctx.candidates:
        if options.get(candidate.id):
            continue
        counts = rejections.get(candidate.id, {})
        details = [f"{reason} ({count} combination(s))"
                   for reason, count in sorted(counts.items(), key=lambda kv: -kv[1])[:5]]
        reason = (max(counts.items(), key=lambda kv: kv[1])[0] if counts
                  else "No panel/date/slot combination exists in the scheduling window")
        unscheduled[candidate.id] = UnscheduledCandidate(
            candidate_id=candidate.id,
            reason=f"No feasible slot: {reason}",
            details=details or ["No faculty free slots were available in the date range"],
        )
    return dict(options), unscheduled


def _provisional_members(panel: PanelSpec, eligible: list[int], required: int) -> list[int]:
    """A representative, legally sized member subset used for pre-scoring."""
    mandatory = [fid for fid in eligible if fid in panel.mandatory_ids]
    optional = [fid for fid in eligible if fid not in panel.mandatory_ids]
    target = max(required, len(mandatory))
    chosen = mandatory + optional[: max(0, target - len(mandatory))]
    return sorted(chosen)


def domain_size(options: dict[int, list[SlotOption]], candidate: CandidateSpec) -> int:
    return len(options.get(candidate.id, ()))
