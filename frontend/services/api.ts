// frontend/services/api.ts

/**
 * Client API (apiFetch)
 *
 * Rôle :
 * - Centraliser tous les appels HTTP du front vers le backend.
 * - Normaliser les headers (JSON, Accept) + tracer chaque requête via X-Request-Id.
 * - Gérer l’auth “light” (X-API-Key + X-Actor) uniquement quand c’est nécessaire.
 * - Uniformiser les erreurs : on remonte toujours un message lisible côté UI.
 *
 * Données attendues (env) :
 * - VITE_API_URL (recommandé) : base URL du backend (ex: http://127.0.0.1:8000)
 * - VITE_API_BASE_URL (fallback legacy)
 * - VITE_API_KEY (optionnel) : clé API si endpoints protégés
 * - VITE_ACTOR (optionnel) : identifiant “qui agit” (audit / logs côté backend)
 *
 * Sorties :
 * - apiFetch<T>(path, init, opts) -> Promise<T>
 * - En cas d’erreur HTTP : throw d’un objet enrichi { status, message, request_id, ...payload }
 *
 * Hypothèses importantes :
 * - Les réponses backend sont majoritairement JSON.
 * - Si la réponse n’est pas JSON, on garde le texte brut (utile pour debug).
 */

const API_BASE =
  (import.meta as any).env?.VITE_API_URL?.toString()?.replace(/\/+$/, "") ||
  (import.meta as any).env?.VITE_API_BASE_URL?.toString()?.replace(/\/+$/, "") ||
  "http://127.0.0.1:8000";

const API_KEY = (import.meta as any).env?.VITE_API_KEY?.toString() || "";
const ACTOR = (import.meta as any).env?.VITE_ACTOR?.toString() || "admin-demo";

/**
 * makeRequestId(prefix)
 * - Génère un identifiant de requête unique côté UI.
 *
 * Pourquoi ?
 * - Permet de corréler facilement : logs front ↔ logs backend.
 * - Si le navigateur supporte crypto.randomUUID → ID robuste.
 * - Sinon fallback (timestamp + random) suffisant pour la trace.
 */
function makeRequestId(prefix = "rid") {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}-${(crypto as any).randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

/**
 * apiFetch<T>(path, init, opts)
 * - Wrapper fetch “opinionated” pour l’app.
 *
 * Comportement :
 * - Ajoute automatiquement :
 *   - Accept: application/json
 *   - Content-Type: application/json (si body et pas déjà défini)
 *   - X-Request-Id: <rid> (traçabilité)
 * - Mode auth (opts.auth=true) :
 *   - X-API-Key (si dispo)
 *   - X-Actor (audit : qui déclenche l’action)
 *
 * Gestion des erreurs :
 * - On lit toujours le body (text), puis on tente de parser en JSON.
 * - Si res.ok = false :
 *   - on construit un message prioritaire :
 *     1) parsed.error.message
 *     2) texte brut si string
 *     3) fallback "HTTP <status>"
 *   - on throw un objet enrichi, incluant request_id (backend ou rid UI)
 */
export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
  opts: { auth?: boolean; requestId?: string; actor?: string } = {}
): Promise<T> {
  const rid = opts.requestId || makeRequestId("ui");
  const headers = new Headers(init.headers || {});

  //  JSON par défaut si body (évite les "415 Unsupported Media Type")
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  headers.set("Accept", "application/json");
  headers.set("X-Request-Id", rid);

  //  On n’envoie les headers “auth” que quand c’est explicitement demandé.
  if (opts.auth) {
    if (API_KEY) headers.set("X-API-Key", API_KEY);
    headers.set("X-Actor", opts.actor || ACTOR);
  }

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });

  // On lit le body quoiqu’il arrive (utile pour erreurs + debug)
  const raw = await res.text();

  // Parse best-effort : JSON si possible, sinon texte brut
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
