// frontend/services/api.ts
const API_BASE =
  (import.meta as any).env?.VITE_API_URL?.toString()?.replace(/\/+$/, "") ||
  (import.meta as any).env?.VITE_API_BASE_URL?.toString()?.replace(/\/+$/, "") ||
  "http://127.0.0.1:8000";

const API_KEY = (import.meta as any).env?.VITE_API_KEY?.toString() || "";
const ACTOR = (import.meta as any).env?.VITE_ACTOR?.toString() || "admin-demo";

function makeRequestId(prefix = "rid") {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}-${(crypto as any).randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
  opts: { auth?: boolean; requestId?: string; actor?: string } = {}
): Promise<T> {
  const rid = opts.requestId || makeRequestId("ui");
  const headers = new Headers(init.headers || {});

  // JSON par défaut si body
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  headers.set("Accept", "application/json");
  headers.set("X-Request-Id", rid);

  if (opts.auth) {
    if (API_KEY) headers.set("X-API-Key", API_KEY);
    headers.set("X-Actor", opts.actor || ACTOR);
  }

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });

  const raw = await res.text();
  let parsed: any = null;
  try {
    parsed = raw ? JSON.parse(raw) : null;
  } catch {
    parsed = raw;
  }

  if (!res.ok) {
    // Normalisation: on renvoie toujours un objet avec message lisible
    const message =
      parsed?.error?.message ||
      (typeof parsed === "string" ? parsed : null) ||
      `HTTP ${res.status}`;

    throw { ...parsed, status: res.status, message, request_id: parsed?.error?.request_id || rid };
  }

  return parsed as T;
}
