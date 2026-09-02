"""Domain generation: every legal candidate x panel x time-slot combination.

This is step 5-7 of the documented algorithm - build the combinations, drop the
ones violating hard constraints, and pre-score the survivors so the solver can
explore the most promising placements first.
"""
from __future__ import annotations

import heapq
from collections import defaultdict
from datetime import date

from app.scheduling.constraints import (evaluate_faculty, evaluate_panel,
                                        evaluate_time)
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
    """Return feasible options per candidate plus reasons for empty domains.

    Three things keep this affordable on large instances:

    * the slot grid is built once per (panel, day) and shared by every candidate;
    * constraint rules are evaluated at the coarsest level they depend on - once
      per (candidate, panel) for panel rules, once per (candidate, day, slot) for
      time rules - instead of once per full combination;
    * each candidate keeps only its best `max_options_per_candidate` options in a
      bounded heap, so memory tracks the cap rather than the cross-product.
    """
    window = _day_window(ctx)
    cap = max(1, ctx.options.max_options_per_candidate)
    # candidate_id -> min-heap of (score, tiebreak, option), smallest score first
    heaps: dict[int, list[tuple[float, tuple, SlotOption]]] = defaultdict(list)
    rejections: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    # Slot grids are identical for every candidate, so compute them once.
    panel_slots: dict[tuple[int, date], list[Interval]] = {}
    for panel in ctx.panels:
        for day in ctx.options.dates:
            panel_slots[(panel.id, day)] = _panel_candidate_slots(ctx, panel, day, window)

    # Eligible members per (panel, day, slot) - independent of the candidate.
    eligibility: dict[tuple[int, date, int, int], list[int]] = {}
    for panel in ctx.panels:
        for day in ctx.options.dates:
            for slot in panel_slots[(panel.id, day)]:
                eligibility[(panel.id, day, slot.start, slot.end)] = [
                    fid for fid in panel.member_ids
                    if ctx.faculty.get(fid) and ctx.faculty[fid].is_free(day, slot)]

    # The faculty rules read only the panel, the slot and the candidate's
    # *department* - never the candidate itself - so their outcome repeats across
    # every candidate in a department.  Caching on that is the difference between
    # one evaluation per combination and one per (panel, slot, department).
    # A constraint scoped to an individual candidate would break that assumption,
    # so the cache is disabled when one exists.
    candidate_scoped = any(c.scope.get("candidate_id") is not None
                           for c in ctx.constraints)
    faculty_cache: dict[tuple, tuple] = {}

    for candidate in ctx.candidates:
        # Time rules are panel-independent, so cache them across panels.
        time_cache: dict[tuple[date, int, int], tuple] = {}
        for panel in ctx.panels:
            required = max(1, panel.minimum_panel_size)
            panel_ok, panel_outcomes, panel_reason = evaluate_panel(
                ctx, candidate, panel, ctx.options.dates[0],
                Interval(0, ctx.options.duration_minutes)) if ctx.options.dates else (
                    True, [], None)
            if not panel_ok:
                rejections[candidate.id][
                    panel_reason or "Panel rejected by a hard constraint"] += len(
                        ctx.options.dates)
                continue
            for day in ctx.options.dates:
                if day in candidate.blocked_dates:
                    rejections[candidate.id]["Candidate blocked this date"] += 1
                    continue
                for slot in panel_slots[(panel.id, day)]:
                    if not candidate.is_available(day, slot):
                        rejections[candidate.id]["Outside candidate availability"] += 1
                        continue
                    eligible = eligibility[(panel.id, day, slot.start, slot.end)]
                    if len(eligible) < required:
                        rejections[candidate.id][
                            f"Panel {panel.code} had fewer than {required} free faculty"] += 1
                        continue
                    if not panel.mandatory_ids.issubset(set(eligible)):
                        rejections[candidate.id][
                            f"Mandatory member of panel {panel.code} unavailable"] += 1
                        continue
                    key = (day, slot.start, slot.end)
                    cached = time_cache.get(key)
                    if cached is None:
                        cached = evaluate_time(ctx, candidate, panel, day, slot)
                        time_cache[key] = cached
                    time_ok, time_outcomes, time_reason = cached
                    if not time_ok:
                        rejections[candidate.id][
                            time_reason or "Hard constraint violated"] += 1
                        continue
                    provisional = _provisional_members(panel, eligible, required)
                    fac_key = (panel.id, day, slot.start, slot.end,
                               candidate.department)
                    fac_cached = None if candidate_scoped else faculty_cache.get(fac_key)
                    if fac_cached is None:
                        fac_cached = evaluate_faculty(
                            ctx, candidate, panel, day, slot, provisional)
                        if not candidate_scoped:
                            faculty_cache[fac_key] = fac_cached
                    fac_ok, fac_outcomes, fac_reason = fac_cached
                    if not fac_ok:
                        rejections[candidate.id][
                            fac_reason or "Hard constraint violated"] += 1
                        continue
                    slot_outcomes = time_outcomes + panel_outcomes
                    outcomes = slot_outcomes + fac_outcomes
                    score = sum(o.score for o in outcomes)
                    option = SlotOption(
                        candidate_id=candidate.id, panel_id=panel.id, day=day,
                        slot=slot, eligible_faculty_ids=eligible,
                        required_size=required, score=score, outcomes=outcomes,
                        slot_outcomes=slot_outcomes)
                    # Bounded: keep only the best `cap` options per candidate.
                    # Tie-break on earliest date/time so the kept set is stable.
                    entry = (score, (-day.toordinal(), -slot.start, -panel.id), option)
                    bucket = heaps[candidate.id]
                    if len(bucket) < cap:
                        heapq.heappush(bucket, entry)
                    elif entry > bucket[0]:
                        heapq.heapreplace(bucket, entry)

    options: dict[int, list[SlotOption]] = {}
    for candidate_id, bucket in heaps.items():
        if not bucket:
            continue
        ordered = sorted(bucket, key=lambda e: (-e[0], e[2].day, e[2].slot.start,
                                                e[2].panel_id))
        options[candidate_id] = [entry[2] for entry in ordered]

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
    return options, unscheduled


def _provisional_members(panel: PanelSpec, eligible: list[int], required: int) -> list[int]:
    """A representative, legally sized member subset used for pre-scoring."""
    mandatory = [fid for fid in eligible if fid in panel.mandatory_ids]
    optional = [fid for fid in eligible if fid not in panel.mandatory_ids]
    target = max(required, len(mandatory))
    chosen = mandatory + optional[: max(0, target - len(mandatory))]
    return sorted(chosen)


def domain_size(options: dict[int, list[SlotOption]], candidate: CandidateSpec) -> int:
    return len(options.get(candidate.id, ()))
