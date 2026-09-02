import * as React from "react";

import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const TONES = {
  brand: "bg-[var(--color-brand-light)] text-[var(--color-brand-dark)]",
  success: "bg-[var(--color-success-light)] text-[var(--color-success)]",
  warning: "bg-[var(--color-warning-light)] text-[var(--color-warning)]",
  danger: "bg-[var(--color-danger-light)] text-[var(--color-danger)]",
  info: "bg-[var(--color-info-light)] text-[var(--color-info)]",
  neutral: "bg-slate-100 text-slate-600",
} as const;

export function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  tone = "brand",
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
  icon?: React.ComponentType<{ className?: string }>;
  tone?: keyof typeof TONES;
}) {
  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-[11px] font-medium uppercase tracking-wide text-slate-500">
            {label}
          </p>
          <p className="mt-1.5 text-xl font-semibold text-slate-900">{value}</p>
          {hint ? <p className="mt-0.5 text-[11px] text-slate-400">{hint}</p> : null}
        </div>
        {Icon ? (
          <div
            className={cn(
              "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg",
              TONES[tone],
            )}
          >
            <Icon className="h-4 w-4" />
          </div>
        ) : null}
      </div>
    </Card>
  );
}
