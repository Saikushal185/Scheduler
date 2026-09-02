"use client";

import { LogOut, Menu, RefreshCw } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { clearSession, getStoredUser } from "@/lib/api";
import type { User } from "@/lib/types";
import { initials } from "@/lib/utils";

export function Topbar({
  title,
  description,
  actions,
  onMenu,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  onMenu: () => void;
}) {
  const router = useRouter();
  const client = useQueryClient();
  const user = getStoredUser<User>();

  return (
    <header className="sticky top-0 z-30 flex min-h-14 flex-wrap items-center gap-3 border-b border-[var(--color-border)] bg-white/95 px-4 py-2.5 backdrop-blur lg:px-6">
      <button
        onClick={onMenu}
        className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100 lg:hidden"
        aria-label="Toggle navigation"
      >
        <Menu className="h-4 w-4" />
      </button>

      <div className="min-w-0 flex-1">
        <h1 className="truncate text-sm font-semibold text-slate-900">{title}</h1>
        {description ? (
          <p className="truncate text-xs text-slate-500">{description}</p>
        ) : null}
      </div>

      <div className="flex items-center gap-2">
        {actions}
        <Button
          variant="ghost"
          size="icon"
          title="Refresh data"
          onClick={() => client.invalidateQueries()}
        >
          <RefreshCw className="h-4 w-4" />
        </Button>
        <div className="flex items-center gap-2 border-l border-[var(--color-border)] pl-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-[var(--color-brand-light)] text-[11px] font-semibold text-[var(--color-brand-dark)]">
            {initials(user?.full_name)}
          </div>
          <div className="hidden leading-tight sm:block">
            <p className="text-xs font-medium text-slate-800">
              {user?.full_name ?? "Signed in"}
            </p>
            <p className="text-[10px] text-slate-400">{user?.role ?? ""}</p>
          </div>
          <Button
            variant="ghost"
            size="icon"
            title="Sign out"
            onClick={() => {
              clearSession();
              router.push("/login");
            }}
          >
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </header>
  );
}
