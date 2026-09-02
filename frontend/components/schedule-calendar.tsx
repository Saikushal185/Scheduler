"use client";

import dayGridPlugin from "@fullcalendar/daygrid";
import interactionPlugin from "@fullcalendar/interaction";
import FullCalendar from "@fullcalendar/react";
import timeGridPlugin from "@fullcalendar/timegrid";
import * as React from "react";

import type { CalendarEvent } from "@/lib/types";

const STATUS_COLOURS: Record<string, string> = {
  SCHEDULED: "#2f4bd8",
  RESCHEDULED: "#2b7fbf",
  COMPLETED: "#0f9d58",
  PENDING: "#d98324",
  CONFLICT: "#d64545",
  CANCELLED: "#98a2b3",
  UNSCHEDULED: "#98a2b3",
};

export function ScheduleCalendar({
  events,
  initialView = "timeGridWeek",
  initialDate,
  onSelect,
}: {
  events: CalendarEvent[];
  initialView?: "timeGridDay" | "timeGridWeek" | "dayGridMonth";
  initialDate?: string;
  onSelect?: (interviewId: number) => void;
}) {
  const mapped = React.useMemo(
    () =>
      events.map((event) => ({
        id: String(event.id),
        title: `${event.candidate_name}${event.panel_name ? ` · ${event.panel_name}` : ""}`,
        start: event.start,
        end: event.end,
        backgroundColor: event.has_conflict
          ? STATUS_COLOURS.CONFLICT
          : (STATUS_COLOURS[event.status] ?? "#2f4bd8"),
        borderColor: "transparent",
        textColor: "#fff",
        extendedProps: event,
      })),
    [events],
  );

  return (
    <FullCalendar
      plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
      initialView={initialView}
      initialDate={initialDate}
      headerToolbar={{
        left: "prev,next today",
        center: "title",
        right: "timeGridDay,timeGridWeek,dayGridMonth",
      }}
      buttonText={{ today: "Today", day: "Day", week: "Week", month: "Month" }}
      events={mapped}
      height="auto"
      expandRows
      nowIndicator
      weekends
      allDaySlot={false}
      slotMinTime="07:00:00"
      slotMaxTime="21:00:00"
      slotDuration="00:30:00"
      eventClick={(info) => onSelect?.(Number(info.event.id))}
      eventContent={(arg) => {
        const data = arg.event.extendedProps as CalendarEvent;
        return (
          <div className="overflow-hidden leading-tight">
            <p className="truncate font-semibold">
              {data.is_locked ? "🔒 " : ""}
              {data.candidate_name}
            </p>
            <p className="truncate opacity-90">{arg.timeText}</p>
            {data.panel_name ? (
              <p className="truncate opacity-80">{data.panel_name}</p>
            ) : null}
          </div>
        );
      }}
    />
  );
}
