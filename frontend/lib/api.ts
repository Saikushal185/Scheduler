"use client";

/** Typed fetch wrapper around the FastAPI backend. */

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "/api/v1";

const TOKEN_KEY = "interview_scheduler_token";
const USER_KEY = "interview_scheduler_user";

export class ApiError extends Error {
  status: number;
  code: string;
  details: unknown;

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }

  /** Flattens backend `details` into readable lines. */
  get detailLines(): string[] {
    if (!this.details) return [];
    if (Array.isArray(this.details)) {
      return this.details.map((item) =>
        typeof item === "string"
          ? item
          : typeof item === "object" && item !== null && "message" in item
            ? String((item as { message: unknown }).message)
            : JSON.stringify(item),
      );
    }
    return [typeof this.details === "string" ? this.details : JSON.stringify(this.details)];
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setSession(token: string, user: unknown) {
  window.localStorage.setItem(TOKEN_KEY, token);
  window.localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession() {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
}

export function getStoredUser<T>(): T | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

type Query = Record<string, string | number | boolean | undefined | null>;

function buildUrl(path: string, query?: Query): string {
  const url = new URL(`${BASE_URL}${path}`, window.location.origin);
  if (query) {
    Object.entries(query).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, String(value));
      }
    });
  }
  return url.toString();
}

async function handle<T>(response: Response): Promise<T> {
  if (response.status === 204) return undefined as T;
  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;
  if (!response.ok) {
    if (response.status === 401 && typeof window !== "undefined") {
      clearSession();
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    throw new ApiError(
      response.status,
      payload?.error ?? "error",
      payload?.message ?? response.statusText,
      payload?.details,
    );
  }
  return payload as T;
}

async function request<T>(
  method: string,
  path: string,
  options: { body?: unknown; query?: Query } = {},
): Promise<T> {
  const token = getToken();
  const response = await fetch(buildUrl(path, options.query), {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    cache: "no-store",
  });
  return handle<T>(response);
}

export const api = {
  get: <T>(path: string, query?: Query) => request<T>("GET", path, { query }),
  post: <T>(path: string, body?: unknown, query?: Query) =>
    request<T>("POST", path, { body, query }),
  put: <T>(path: string, body?: unknown, query?: Query) =>
    request<T>("PUT", path, { body, query }),
  delete: <T>(path: string, query?: Query) => request<T>("DELETE", path, { query }),

  /** Multipart upload used by the Data Upload page. */
  upload: async <T>(path: string, file: File, fields?: Record<string, string>) => {
    const token = getToken();
    const form = new FormData();
    form.append("file", file);
    Object.entries(fields ?? {}).forEach(([key, value]) => form.append(key, value));
    const response = await fetch(buildUrl(path), {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      body: form,
    });
    return handle<T>(response);
  },
};

export { BASE_URL };
