import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium leading-4",
  {
    variants: {
      tone: {
        neutral: "bg-slate-100 text-slate-700",
        brand: "bg-[var(--color-brand-light)] text-[var(--color-brand-dark)]",
        success: "bg-[var(--color-success-light)] text-[var(--color-success)]",
        warning: "bg-[var(--color-warning-light)] text-[var(--color-warning)]",
        danger: "bg-[var(--color-danger-light)] text-[var(--color-danger)]",
        info: "bg-[var(--color-info-light)] text-[var(--color-info)]",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}

const STATUS_TONES: Record<string, BadgeProps["tone"]> = {
  SCHEDULED: "brand",
  RESCHEDULED: "info",
  COMPLETED: "success",
  PENDING: "warning",
  CONFLICT: "danger",
  CANCELLED: "neutral",
  UNSCHEDULED: "danger",
  WITHDRAWN: "neutral",
  HARD: "danger",
  HIGH: "warning",
  MEDIUM: "info",
  LOW: "neutral",
  FLEXIBLE: "success",
  AVAILABLE: "success",
  UNAVAILABLE: "danger",
  TENTATIVE: "warning",
  SELECT: "success",
  HOLD: "warning",
  REJECT: "danger",
};

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  return (
    <Badge tone={STATUS_TONES[status] ?? "neutral"} className={className}>
      {status.replace(/_/g, " ").toLowerCase()}
    </Badge>
  );
}
