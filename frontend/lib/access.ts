/**
 * Which routes each role may reach.
 *
 * One source of truth shared by the sidebar and the layout guard, so a link can
 * never appear that the guard would bounce, and a route can never be reachable
 * that the nav hides. This mirrors the backend policy in
 * `app/core/permissions.py` - the server is still the authority; this only
 * decides what to render.
 */
import type { UserRole } from "@/lib/types";

export const ADMIN_ROLES: UserRole[] = ["ADMIN", "COORDINATOR"];

/** Route prefix -> roles allowed to open it. */
export const ROUTE_ACCESS: { prefix: string; roles: UserRole[] }[] = [
  { prefix: "/dashboard", roles: ["ADMIN", "COORDINATOR", "VIEWER"] },
  { prefix: "/upload", roles: ADMIN_ROLES },
  { prefix: "/users", roles: ["ADMIN"] },
  { prefix: "/candidates", roles: ["ADMIN", "COORDINATOR", "FACULTY"] },
  { prefix: "/faculty", roles: ["ADMIN", "COORDINATOR", "FACULTY"] },
  { prefix: "/availability", roles: ["ADMIN", "COORDINATOR", "FACULTY"] },
  { prefix: "/free-slots", roles: ["ADMIN", "COORDINATOR", "FACULTY"] },
  { prefix: "/panels", roles: ["ADMIN", "COORDINATOR", "FACULTY"] },
  { prefix: "/scheduler", roles: ADMIN_ROLES },
  { prefix: "/schedule", roles: ["ADMIN", "COORDINATOR", "FACULTY"] },
  { prefix: "/evaluations", roles: ["ADMIN", "COORDINATOR", "FACULTY"] },
  { prefix: "/analytics", roles: ["ADMIN", "COORDINATOR", "FACULTY", "VIEWER"] },
  { prefix: "/settings", roles: ADMIN_ROLES },
  { prefix: "/my-schedule", roles: ["FACULTY"] },
  { prefix: "/my-interview", roles: ["STUDENT"] },
];

/** Where each role lands after signing in. */
export const HOME_ROUTE: Record<UserRole, string> = {
  ADMIN: "/dashboard",
  COORDINATOR: "/dashboard",
  VIEWER: "/dashboard",
  FACULTY: "/my-schedule",
  STUDENT: "/my-interview",
};

export function canAccess(role: UserRole | undefined, pathname: string): boolean {
  if (!role) return false;
  // Longest prefix wins so "/schedule" does not shadow "/scheduler".
  const match = [...ROUTE_ACCESS]
    .sort((a, b) => b.prefix.length - a.prefix.length)
    .find((entry) => pathname === entry.prefix || pathname.startsWith(`${entry.prefix}/`));
  return match ? match.roles.includes(role) : true;
}

export function homeFor(role: UserRole | undefined): string {
  return role ? (HOME_ROUTE[role] ?? "/dashboard") : "/login";
}

export const isAdmin = (role?: UserRole) => !!role && ADMIN_ROLES.includes(role);
