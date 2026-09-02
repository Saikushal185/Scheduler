"use client";

import { CheckCircle2, X, XCircle } from "lucide-react";
import * as React from "react";

type Toast = { id: number; tone: "success" | "error"; message: string };

const ToastContext = React.createContext<{
  notify: (message: string, tone?: Toast["tone"]) => void;
}>({ notify: () => undefined });

export function useToast() {
  return React.useContext(ToastContext);
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = React.useState<Toast[]>([]);

  const notify = React.useCallback(
    (message: string, tone: Toast["tone"] = "success") => {
      const id = Date.now() + Math.random();
      setToasts((current) => [...current, { id, tone, message }]);
      window.setTimeout(
        () => setToasts((current) => current.filter((item) => item.id !== id)),
        5000,
      );
    },
    [],
  );

  return (
    <ToastContext.Provider value={{ notify }}>
      {children}
      <div className="pointer-events-none fixed bottom-5 right-5 z-[100] flex w-80 flex-col gap-2">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`pointer-events-auto flex items-start gap-2 rounded-lg border px-3.5 py-3 text-xs shadow-lg ${
              toast.tone === "success"
                ? "border-[var(--color-success)]/30 bg-white text-slate-700"
                : "border-[var(--color-danger)]/30 bg-white text-slate-700"
            }`}
          >
            {toast.tone === "success" ? (
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-success)]" />
            ) : (
              <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-danger)]" />
            )}
            <p className="flex-1 leading-relaxed">{toast.message}</p>
            <button
              onClick={() =>
                setToasts((current) => current.filter((item) => item.id !== toast.id))
              }
              className="text-slate-400 hover:text-slate-600"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
