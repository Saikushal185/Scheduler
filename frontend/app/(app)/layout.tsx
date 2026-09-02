"use client";

import { usePathname, useRouter } from "next/navigation";
import * as React from "react";

import { PageMetaProvider } from "@/components/layout/page";
import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";
import { LoadingState } from "@/components/ui/feedback";
import { canAccess, homeFor } from "@/lib/access";
import { getStoredUser, getToken } from "@/lib/api";
import type { User } from "@/lib/types";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = React.useState(false);
  const [menuOpen, setMenuOpen] = React.useState(false);
  const [meta, setMeta] = React.useState<{
    title: string;
    description?: string;
    actions?: React.ReactNode;
  }>({ title: "Dashboard" });

  React.useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    // Bounce to the caller's own home rather than rendering a page whose every
    // request would come back 403.
    const role = getStoredUser<User>()?.role;
    if (!canAccess(role, pathname)) {
      router.replace(homeFor(role));
      return;
    }
    setReady(true);
  }, [router, pathname]);

  const value = React.useMemo(() => ({ setMeta }), []);

  if (!ready) return <LoadingState label="Checking your session..." />;

  return (
    <PageMetaProvider value={value}>
      <div className="min-h-screen">
        <Sidebar open={menuOpen} onNavigate={() => setMenuOpen(false)} />
        {menuOpen ? (
          <div
            className="fixed inset-0 z-30 bg-slate-900/20 lg:hidden"
            onClick={() => setMenuOpen(false)}
          />
        ) : null}
        <div className="lg:pl-60">
          <Topbar
            title={meta.title}
            description={meta.description}
            actions={meta.actions}
            onMenu={() => setMenuOpen((open) => !open)}
          />
          <main className="px-4 py-5 lg:px-6">{children}</main>
        </div>
      </div>
    </PageMetaProvider>
  );
}
