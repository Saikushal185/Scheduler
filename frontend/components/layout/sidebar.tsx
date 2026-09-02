"use client";

import {
  BarChart3,
  CalendarClock,
  CalendarDays,
  ClipboardCheck,
  Clock4,
  LayoutDashboard,
  Settings as SettingsIcon,
  ShieldCheck,
  Sparkles,
  Timer,
  Upload,
  Users,
  UsersRound,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import * as React from "react";

import { canAccess } from "@/lib/access";
import { getStoredUser } from "@/lib/api";
import type { User } from "@/lib/types";
import { cn } from "@/lib/utils";

const NAV = [
  { section: "Me", items: [
    { href: "/my-schedule", label: "My Schedule", icon: CalendarDays },
    { href: "/my-interview", label: "My Interview", icon: CalendarDays },
  ]},
  { section: "Overview", items: [
    { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
    { href: "/upload", label: "Data / Excel Upload", icon: Upload },
  ]},
  { section: "Master data", items: [
    { href: "/candidates", label: "Candidates", icon: Users },
    { href: "/faculty", label: "Faculty", icon: UsersRound },
    { href: "/availability", label: "Faculty Availability", icon: Clock4 },
    { href: "/free-slots", label: "Free Slots", icon: Timer },
    { href: "/panels", label: "Panel Groups", icon: ClipboardCheck },
  ]},
  { section: "Scheduling", items: [
    { href: "/scheduler", label: "Automated Scheduler", icon: Sparkles },
    { href: "/schedule", label: "Interview Schedule", icon: CalendarDays },
  ]},
  { section: "Results", items: [
    { href: "/evaluations", label: "Evaluation Management", icon: ClipboardCheck },
    { href: "/analytics", label: "Analytics & Reports", icon: BarChart3 },
  ]},
  { section: "Administration", items: [
    { href: "/users", label: "User Accounts", icon: ShieldCheck },
    { href: "/settings", label: "Settings", icon: SettingsIcon },
  ]},
];

export function Sidebar({ open, onNavigate }: { open: boolean; onNavigate?: () => void }) {
  const pathname = usePathname();
  const role = getStoredUser<User>()?.role;

  // Hide what this role cannot open, and drop sections left empty by that.
  const nav = React.useMemo(
    () =>
      NAV.map((group) => ({
        ...group,
        items: group.items.filter((item) => canAccess(role, item.href)),
      })).filter((group) => group.items.length > 0),
    [role],
  );

  return (
    <aside
      className={cn(
        "fixed inset-y-0 left-0 z-40 flex w-60 flex-col border-r border-[var(--color-border)] bg-white transition-transform lg:translate-x-0",
        open ? "translate-x-0" : "-translate-x-full",
      )}
    >
      <div className="flex h-14 items-center gap-2.5 border-b border-[var(--color-border)] px-5">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--color-brand)] text-white">
          <CalendarClock className="h-4 w-4" />
        </div>
        <div className="leading-tight">
          <p className="text-[13px] font-semibold text-slate-900">Interview Suite</p>
          <p className="text-[10px] text-slate-400">Scheduling &amp; Evaluation</p>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-4">
        {nav.map((group) => (
          <div key={group.section} className="mb-5">
            <p className="mb-1.5 px-2 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
              {group.section}
            </p>
            <ul className="space-y-0.5">
              {group.items.map((item) => {
                const active = pathname === item.href;
                const Icon = item.icon;
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      onClick={onNavigate}
                      className={cn(
                        "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] font-medium transition-colors",
                        active
                          ? "bg-[var(--color-brand-light)] text-[var(--color-brand-dark)]"
                          : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
                      )}
                    >
                      <Icon className="h-4 w-4 shrink-0" />
                      <span className="truncate">{item.label}</span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>
    </aside>
  );
}
