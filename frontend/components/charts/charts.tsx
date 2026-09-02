"use client";

import * as React from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export const PALETTE = [
  "#2f4bd8", "#0f9d58", "#d98324", "#2b7fbf", "#8b5cf6",
  "#d64545", "#0891b2", "#65a30d",
];

const AXIS = { fontSize: 11, fill: "#6b7280" };
const GRID = "#e3e6ef";

const tooltipStyle = {
  contentStyle: {
    borderRadius: 8,
    border: "1px solid #e3e6ef",
    fontSize: 12,
    boxShadow: "0 4px 12px rgba(16,24,40,0.08)",
  },
} as const;

export function ChartFrame({
  height = 260,
  children,
}: {
  height?: number;
  children: React.ReactElement;
}) {
  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer width="100%" height="100%">
        {children}
      </ResponsiveContainer>
    </div>
  );
}

export function SimpleBarChart({
  data,
  xKey,
  bars,
  height = 260,
  layout = "horizontal",
}: {
  data: Record<string, unknown>[];
  xKey: string;
  bars: { key: string; name: string; color?: string }[];
  height?: number;
  layout?: "horizontal" | "vertical";
}) {
  return (
    <ChartFrame height={height}>
      <BarChart data={data} layout={layout} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={layout === "vertical"} />
        {layout === "horizontal" ? (
          <>
            <XAxis dataKey={xKey} tick={AXIS} tickLine={false} axisLine={{ stroke: GRID }} />
            <YAxis tick={AXIS} tickLine={false} axisLine={false} allowDecimals={false} />
          </>
        ) : (
          <>
            <XAxis type="number" tick={AXIS} tickLine={false} axisLine={false} />
            <YAxis
              type="category"
              dataKey={xKey}
              tick={AXIS}
              tickLine={false}
              axisLine={false}
              width={130}
            />
          </>
        )}
        <Tooltip {...tooltipStyle} />
        {bars.length > 1 ? <Legend wrapperStyle={{ fontSize: 11 }} /> : null}
        {bars.map((bar, index) => (
          <Bar
            key={bar.key}
            dataKey={bar.key}
            name={bar.name}
            fill={bar.color ?? PALETTE[index % PALETTE.length]}
            radius={layout === "horizontal" ? [4, 4, 0, 0] : [0, 4, 4, 0]}
            maxBarSize={38}
          />
        ))}
      </BarChart>
    </ChartFrame>
  );
}

export function SimpleLineChart({
  data,
  xKey,
  lines,
  height = 260,
}: {
  data: Record<string, unknown>[];
  xKey: string;
  lines: { key: string; name: string; color?: string }[];
  height?: number;
}) {
  return (
    <ChartFrame height={height}>
      <LineChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
        <XAxis dataKey={xKey} tick={AXIS} tickLine={false} axisLine={{ stroke: GRID }} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} allowDecimals={false} />
        <Tooltip {...tooltipStyle} />
        {lines.length > 1 ? <Legend wrapperStyle={{ fontSize: 11 }} /> : null}
        {lines.map((line, index) => (
          <Line
            key={line.key}
            type="monotone"
            dataKey={line.key}
            name={line.name}
            stroke={line.color ?? PALETTE[index % PALETTE.length]}
            strokeWidth={2}
            dot={{ r: 2.5 }}
            activeDot={{ r: 4 }}
          />
        ))}
      </LineChart>
    </ChartFrame>
  );
}

export function MetricRadarChart({
  data,
  height = 300,
  series,
}: {
  data: { metric: string; value: number; fullMark: number }[];
  height?: number;
  series?: string;
}) {
  return (
    <ChartFrame height={height}>
      <RadarChart data={data} outerRadius="72%">
        <PolarGrid stroke={GRID} />
        <PolarAngleAxis dataKey="metric" tick={{ fontSize: 10, fill: "#6b7280" }} />
        <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fontSize: 9, fill: "#9ca3af" }} />
        <Radar
          name={series ?? "Score"}
          dataKey="value"
          stroke={PALETTE[0]}
          fill={PALETTE[0]}
          fillOpacity={0.35}
        />
        <Tooltip {...tooltipStyle} />
      </RadarChart>
    </ChartFrame>
  );
}

export function DistributionChart({
  data,
  height = 240,
}: {
  data: { label: string; count: number }[];
  height?: number;
}) {
  return (
    <ChartFrame height={height}>
      <BarChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
        <XAxis dataKey="label" tick={AXIS} tickLine={false} axisLine={{ stroke: GRID }} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} allowDecimals={false} />
        <Tooltip {...tooltipStyle} />
        <Bar dataKey="count" name="Candidates" radius={[4, 4, 0, 0]} maxBarSize={48}>
          {data.map((entry, index) => (
            <Cell key={entry.label} fill={PALETTE[index % PALETTE.length]} />
          ))}
        </Bar>
      </BarChart>
    </ChartFrame>
  );
}
