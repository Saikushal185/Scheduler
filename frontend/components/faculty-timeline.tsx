"use client";

import * as React from "react";

import type { TimelineSegment } from "@/lib/types";
import { formatTime, minutesToHours } from "@/lib/utils";

/**
 * A faculty member's day as a proportional bar.
 *
 * Four states, because "not free" means two different things to whoever is
 * reading the schedule: BOOKED is an actual interview, BUSY is time the faculty
 * member blocked out, FREE is bookable, and the grey track behind everything is
 * time they never declared themselves available for.
 */
export const SEGMENT_STYLES: Record<
  string,
  { colour: string; light: string; label: string }
> = {
  BOOKED: {
    colour: "var(--color-booked)",
    light: "var(--color-booked-light)",
    label: "Booked (interview)",
  },
  BUSY: {
    colour: "var(--color-busy)",
    light: "var(--color-busy-light)",
    label: "Busy (unavailable)",
  },
  FREE: {
    colour: "var(--color-free)",
    light: "var(--color-free-light)",
    label: "Free",
  },
  UNAVAILABLE: {
    colour: "var(--color-neutral)",
    light: "var(--color-neutral-light)",
    label: "Outside working hours",
  },
};

export function TimelineLegend({ className = "" }: { className?: string }) {
  return (
    <div className={`flex flex-wrap items-center gap-x-4 gap-y-1 ${className}`}>
      {Object.entries(SEGMENT_STYLES).map(([kind, style]) => (
        <span key={kind} className="flex items-center gap-1.5 text-[11px] text-slate-500">
          <span
            aria-hidden
            className="h-2.5 w-2.5 rounded-[3px]"
            style={{ background: style.colour }}
          />
          {style.label}
        </span>
      ))}
    </div>
  );
}

export function FacultyTimeline({
  segments,
  dayStart = 8 * 60,
  dayEnd = 19 * 60,
}: {
  segments: TimelineSegment[];
  /** Minutes since midnight; defaults match the working day in settings. */
  dayStart?: number;
  dayEnd?: number;
}) {
  const span = Math.max(1, dayEnd - dayStart);

  return (
    <div
      className="relative h-7 w-full overflow-hidden rounded-md"
      style={{ background: "var(--color-neutral-light)" }}
      role="img"
      aria-label={segments
        .map(
          (s) =>
            `${SEGMENT_STYLES[s.kind]?.label ?? s.kind} ${formatTime(s.start_time)} to ${formatTime(s.end_time)}`,
        )
        .join("; ")}
    >
      {segments.map((segment, index) => {
        const start = Math.max(dayStart, segment.start_minute);
        const end = Math.min(dayEnd, segment.end_minute);
        if (end <= start) return null;
        const left = ((start - dayStart) / span) * 100;
        const width = Math.max(1, ((end - start) / span) * 100);
        const style = SEGMENT_STYLES[segment.kind] ?? SEGMENT_STYLES.UNAVAILABLE;
        const tooltip = [
          style.label,
          `${formatTime(segment.start_time)} - ${formatTime(segment.end_time)}`,
          minutesToHours(segment.duration_minutes),
          segment.label,
          segment.schedule_code,
        ]
          .filter(Boolean)
          .join(" · ");

        return (
          <div
            key={`${segment.kind}-${segment.start_minute}-${index}`}
            title={tooltip}
            className="absolute top-0 flex h-full items-center overflow-hidden rounded-[4px] px-1 text-[9px] font-medium text-white"
            style={{
              left: `${left}%`,
              width: `${width}%`,
              background: style.colour,
              opacity: segment.kind === "FREE" ? 0.85 : 1,
            }}
          >
            {/* Never rely on colour alone: label the block whenever it fits. */}
            {width > 12 ? (
              <span className="truncate">
                {segment.kind === "BOOKED"
                  ? segment.label || formatTime(segment.start_time)
                  : formatTime(segment.start_time)}
              </span>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

/** Compact "3h booked · 1h busy · 4h free" summary for a row. */
export function TimelineTotals({
  booked,
  busy,
  free,
}: {
  booked: number;
  busy: number;
  free: number;
}) {
  const parts: { value: number; kind: string }[] = [
    { value: booked, kind: "BOOKED" },
    { value: busy, kind: "BUSY" },
    { value: free, kind: "FREE" },
  ];
  return (
    <div className="flex flex-wrap items-center gap-2 text-[11px] tabular-nums">
      {parts
        .filter((part) => part.value > 0)
        .map((part) => (
          <span
            key={part.kind}
            className="rounded px-1.5 py-0.5 font-medium"
            style={{
              background: SEGMENT_STYLES[part.kind].light,
              color: SEGMENT_STYLES[part.kind].colour,
            }}
          >
            {minutesToHours(part.value)} {part.kind.toLowerCase()}
          </span>
        ))}
    </div>
  );
}
