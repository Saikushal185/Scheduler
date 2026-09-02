"use client";

import { AlertTriangle, CheckCircle2, Info, Loader2, XCircle } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("h-4 w-4 animate-spin", className)} />;
}

export function LoadingState({ label = "Loading..." }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-12 text-sm text-slate-500">
      <Spinner /> {label}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
  icon: Icon = Info,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
  icon?: React.ComponentType<{ className?: string }>;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
      <Icon className="h-7 w-7 text-slate-300" />
      <p className="text-sm font-medium text-slate-700">{title}</p>
      {description ? (
        <p className="max-w-md text-xs text-slate-500">{description}</p>
      ) : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}

const ALERT_STYLES = {
  info: {
    wrapper: "bg-[var(--color-info-light)] text-[var(--color-info)]",
    Icon: Info,
  },
  success: {
    wrapper: "bg-[var(--color-success-light)] text-[var(--color-success)]",
    Icon: CheckCircle2,
  },
  warning: {
    wrapper: "bg-[var(--color-warning-light)] text-[var(--color-warning)]",
    Icon: AlertTriangle,
  },
  danger: {
    wrapper: "bg-[var(--color-danger-light)] text-[var(--color-danger)]",
    Icon: XCircle,
  },
} as const;

export function Alert({
  tone = "info",
  title,
  children,
  className,
}: {
  tone?: keyof typeof ALERT_STYLES;
  title?: string;
  children?: React.ReactNode;
  className?: string;
}) {
  const { wrapper, Icon } = ALERT_STYLES[tone];
  return (
    <div className={cn("flex gap-2.5 rounded-lg px-3.5 py-3 text-xs", wrapper, className)}>
      <Icon className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="min-w-0 flex-1">
        {title ? <p className="font-semibold">{title}</p> : null}
        {children ? <div className="mt-0.5 leading-relaxed">{children}</div> : null}
      </div>
    </div>
  );
}

export function ErrorState({ error }: { error: unknown }) {
  const message =
    error instanceof Error ? error.message : "Something went wrong loading this view.";
  const details =
    error && typeof error === "object" && "detailLines" in error
      ? ((error as { detailLines: string[] }).detailLines ?? [])
      : [];
  return (
    <Alert tone="danger" title="Request failed" className="m-4">
      <p>{message}</p>
      {details.length ? (
        <ul className="mt-1 list-disc space-y-0.5 pl-4">
          {details.slice(0, 5).map((line, index) => (
            <li key={index}>{line}</li>
          ))}
        </ul>
      ) : null}
    </Alert>
  );
}
