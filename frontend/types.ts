// frontend/types.ts

// ✅ Aligné backend (app/models + endpoints)
export enum RiskLevel {
  LOW = "LOW",
  MEDIUM = "MEDIUM",
  HIGH = "HIGH",
}

export enum AlertStatus {
  A_TRAITER = "A_TRAITER",
  EN_ENQUETE = "EN_ENQUETE",
  CLOTURE = "CLOTURE",
}

// --- Modèles API (backend) ---
export interface Transaction {
  id: string;
  occurred_at: string; // ISO
  amount: string | number; // backend peut renvoyer string (Decimal)
  currency: string;
  merchant_name: string;
  merchant_category: string; // ex: "ecommerce"
  arrondissement: string; // ex: "75010"
  channel: string; // "card"...
  is_online: boolean;
  description?: string | null;
}

export interface RiskScore {
  id: string;
  transaction_id: string;
  score: number;
  model_version: string;
  created_at: string;
}

export interface Alert {
  id: string;
  transaction_id: string;
  risk_score_id?: string | null;
  score_snapshot: number;
  status: AlertStatus | string; // backend renvoie "A_TRAITER" etc (string OK + normalize)
  reason: string;
  created_at: string;
  updated_at: string;
  comment?: string | null;
  handler_name?: string | null;
}

export interface AlertListItem {
  alert: Alert;
  transaction: Transaction;
  risk_score?: RiskScore | null;
}

export interface AlertsListMeta {
  page: number;
  page_size: number;
  total: number;
}

export interface AlertsListResponse {
  data: AlertListItem[];
  meta: AlertsListMeta;
}

export interface ScoreResponse {
  transaction_id: string;
  score: number;
  risk_level: RiskLevel | string;
  factors: string[];
  threshold: number;
  alert?: Alert | null;
}

// --- Dashboard ---
export interface DashboardStats {
  totalTransactionsToday: number;
  openAlerts: number;
  criticalAlerts: number;
  avgResolutionTimeMinutes: number;
}

// --- Types UI (front) ---
// Utilisé par Simulator.tsx : on garde Transaction "backend pure" + on ajoute un bloc risk côté UI.
export type TransactionRiskUI = {
  score: number;
  level: string; // ex: "CRITIQUE" / "OK" (label UI)
  factors: string[];
};

export type TransactionWithRiskUI = Transaction & {
  risk?: TransactionRiskUI;
};

// --- Helpers UI (exports attendus par le front) ---
export const normalizeAlertStatus = (status?: string | null): AlertStatus => {
  const s = (status || "").toUpperCase().trim();

  // compat éventuelle anciens libellés
  const map: Record<string, AlertStatus> = {
    A_TRAITER: AlertStatus.A_TRAITER,
    EN_ENQUETE: AlertStatus.EN_ENQUETE,
    CLOTURE: AlertStatus.CLOTURE,

    // vieux / alternatifs (au cas où)
    NOUVEAU: AlertStatus.A_TRAITER,
    NEW: AlertStatus.A_TRAITER,
    EN_COURS: AlertStatus.EN_ENQUETE,
    IN_REVIEW: AlertStatus.EN_ENQUETE,
    CLOSED: AlertStatus.CLOTURE,
    "CLOTURÉ": AlertStatus.CLOTURE,
    CLOTUREE: AlertStatus.CLOTURE,
  };

  return map[s] || AlertStatus.A_TRAITER;
};

export const getRiskLabel = (level: RiskLevel | string) => {
  const lv = (level || "").toUpperCase();
  if (lv === "HIGH") return "Urgent";
  if (lv === "MEDIUM") return "À vérifier";
  if (lv === "LOW") return "Normal";
  return "Inconnu";
};

export const getRiskColor = (level?: RiskLevel | string) => {
  const lv = (level || "").toUpperCase();
  if (lv === "HIGH") return "text-red-400 bg-red-400/10 border-red-400/20";
  if (lv === "MEDIUM") return "text-amber-400 bg-amber-400/10 border-amber-400/20";
  if (lv === "LOW") return "text-emerald-400 bg-emerald-400/10 border-emerald-400/20";
  return "text-slate-400 bg-slate-400/10 border-slate-400/20";
};

export const getCategoryColor = (cat: string) => {
  const map: Record<string, string> = {
    ecommerce: "bg-indigo-500",
    electronics: "bg-zinc-500",
    hotel: "bg-sky-500",
    travel: "bg-sky-500",
    transport: "bg-blue-500",
    food: "bg-green-500",
    luxury: "bg-purple-600",
    telecom: "bg-cyan-600",
    subscription: "bg-violet-500",
    entertainment: "bg-rose-500",
    health: "bg-emerald-600",
    fuel: "bg-slate-600",
    fashion: "bg-pink-500",
  };
  return map[(cat || "").toLowerCase()] || "bg-slate-500";
};

// --- Helpers robustes (mock / backend) ---
// Permet au Dashboard de fonctionner même si les alertes sont "flatten" (mock) OU "AlertListItem" (backend).

export const pickAlertStatus = (x: any): string =>
  (x?.alert?.status ?? x?.status ?? "") as string;

export const pickAlertScoreSnapshot = (x: any): number =>
  Number(x?.alert?.score_snapshot ?? x?.score_snapshot ?? 0);

export const pickAlertReason = (x: any): string =>
  (x?.alert?.reason ?? x?.reason ?? "") as string;

export const pickAlertCreatedAt = (x: any): string =>
  (x?.alert?.created_at ?? x?.created_at ?? "") as string;

export const pickTransaction = (x: any): Transaction | null =>
  (x?.transaction ?? null) as Transaction | null;
