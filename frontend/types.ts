// frontend/types.ts

/**
 * types.ts
 *
 * Rôle :
 * - Centraliser les types partagés du frontend :
 *   - Modèles alignés sur l’API backend (Transaction, Alert, RiskScore…)
 *   - Types “UI/legacy” utilisés par certains écrans (ex: FullTransactionData)
 *   - Helpers de normalisation (statuts, couleurs, pickers robustes)
 *
 * Objectif produit :
 * - Permettre à l’UI d’être stable même si certaines réponses backend varient
 *   (champs nested vs flat, Decimal en string, statuts différents, etc.).
 *
 * ⚠️ Contrat important :
 * - Scores de risque attendus en 0..100 côté UI (affichage, badges, seuils).
 * - `arrondissement` est généralement un code de type "75010", mais on garde
 *   de la tolérance côté UI (parsing / fallback).
 */

//  Aligné backend (app/models + endpoints)
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

/**
 * Transaction (backend)
 * - Une opération de paiement/flux à analyser.
 *
 * Points d’attention :
 * - `amount` peut être une string (Decimal côté backend) → l’UI cast au besoin.
 * - `arrondissement` est un identifiant de zone (ex: "75010") utilisé pour la carte Paris.
 */
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

/**
 * RiskScore (backend)
 * - Score calculé par le modèle pour une transaction.
 *
 * Hypothèse :
 * - `score` est attendu en 0..100 (affichage UI).
 */
export interface RiskScore {
  id: string;
  transaction_id: string;
  score: number;
  model_version: string;
  created_at: string;
}

/**
 * Alert (backend)
 * - Dossier créé quand un score dépasse le seuil (ou selon règles métier).
 *
 * Points d’attention :
 * - `status` est typé AlertStatus mais on garde `| string` pour tolérer
 *   d’anciens statuts ("CLOSED", "NEW", etc.).
 */
export interface Alert {
  id: string;
  transaction_id: string;
  risk_score_id?: string | null;
  score_snapshot: number;
  status: AlertStatus | string;
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

/**
 * ScoreResponse (backend)
 * - Résultat d’un scoring à la demande.
 *
 * Utilisation :
 * - Simulator : crée une transaction puis score → parfois crée une alerte.
 */
export interface ScoreResponse {
  transaction_id: string;
  score: number;
  risk_level: RiskLevel | string;
  factors: string[];
  threshold: number;
  alert?: Alert | null;
}

// --- Transactions list (backend/mock) ---

/**
 * TransactionListItem
 * - Format “liste” proche de /alerts :
 *   transaction + risk_score + éventuelle alert associée.
 */
export interface TransactionListItem {
  transaction: Transaction;
  risk_score?: RiskScore | null;
  alert?: Alert | null;
}

// meta optionnelle (si paginé)
export interface TransactionsListMeta {
  page?: number;
  page_size?: number;
  total?: number;
}

export interface TransactionsListResponse {
  data: TransactionListItem[];
  meta?: TransactionsListMeta;
}

// --- Dashboard ---

/**
 * DashboardStats (UI)
 * - KPIs principaux affichés sur le Dashboard.
 */
export interface DashboardStats {
  totalTransactionsToday: number;
  openAlerts: number;
  criticalAlerts: number;
  avgResolutionTimeMinutes: number;
}

// --- Types UI (front) ---

/**
 * TransactionRiskUI
 * - Bloc “risk” purement UI :
 *   - `level` peut être un label custom ("CRITIQUE") en plus des niveaux backend.
 */
export type TransactionRiskUI = {
  score: number;
  level: string; // ex: "CRITIQUE" / "OK" (label UI)
  factors: string[];
};

export type TransactionWithRiskUI = Transaction & {
  risk?: TransactionRiskUI;
};

// --- ✅ Legacy type attendu par Transactions.tsx ---

/**
 * FullTransactionData (legacy)
 * - Type “souple” utilisé par des écrans historiques (Transactions, Gemini, ParisMap).
 * - Permet de supporter :
 *   - réponses flat (ancien mock)
 *   - réponses nested (backend /alerts, /transactions)
 *
 *  Règle produit :
 * - On conserve ce type tant que tout n’est pas migré vers TransactionListItem.
 */
export type FullTransactionData = {
  id: string;
  amount: string | number;
  currency?: string;
  merchant_name?: string;
  merchant_category?: string;
  arrondissement?: string;
  channel?: string;
  is_online?: boolean;

  // dates (legacy)
  occurred_at?: string;
  timestamp?: string;

  // risk (legacy)
  risk_score?: number;
  risk_level?: RiskLevel | string;
  score?: number;
  level?: RiskLevel | string;

  // alert (legacy)
  alert_status?: AlertStatus | string;
  status?: AlertStatus | string;

  // map (ParisMap)
  zone_paris?: number;

  // hotspots (ParisMap)
  count?: number;

  // risk (UI/map)
  risk?: { score: number; factors?: string[] };
};

// --- Helpers UI (exports attendus par le front) ---

/**
 * normalizeAlertStatus
 * - Normalise un statut backend/mock vers les 3 états UI.
 *
 * Pourquoi :
 * - Certains écrans reçoivent encore des statuts “historiques” (NEW/CLOSED…).
 * - On garantit un comportement cohérent des tabs (À traiter / En enquête / Clôturé).
 */
export const normalizeAlertStatus = (status?: string | null): AlertStatus => {
  const s = (status || "").toUpperCase().trim();

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

/**
 * getRiskLabel(level)
 * - Convertit un niveau de risque (LOW/MEDIUM/HIGH) en libellé humain.
 *
 * Impact UI :
 * - Utilisé pour les chips “Urgent / À vérifier / Normal”.
 */
export const getRiskLabel = (level: RiskLevel | string) => {
  const lv = (level || "").toUpperCase();
  if (lv === "HIGH") return "Urgent";
  if (lv === "MEDIUM") return "À vérifier";
  if (lv === "LOW") return "Normal";
  return "Inconnu";
};

/**
 * getRiskColor(level)
 * - Renvoie les classes Tailwind (texte + bg + bordure) selon la criticité.
 *
 * Impact UI :
 * - Style cohérent sur Dashboard / Transactions.
 */
export const getRiskColor = (level?: RiskLevel | string) => {
  const lv = (level || "").toUpperCase();
  if (lv === "HIGH") return "text-red-400 bg-red-400/10 border-red-400/20";
  if (lv === "MEDIUM") return "text-amber-400 bg-amber-400/10 border-amber-400/20";
  if (lv === "LOW") return "text-emerald-400 bg-emerald-400/10 border-emerald-400/20";
  return "text-slate-400 bg-slate-400/10 border-slate-400/20";
};

/**
 * getCategoryColor(cat)
 * - Mapping catégorie -> couleur (badge / avatar).
 *
 *  Produit :
 * - Sert à donner un repère visuel rapide (type de commerce).
 * - Si catégorie inconnue → fallback slate.
 */
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

/**
 * Pickers “tolérants”
 * - L’UI consomme parfois :
 *   - x.alert.status (nested)
 *   - ou x.status (flat)
 * - Ces helpers évitent les crashs et uniformisent l’accès aux champs.
 */

export const pickAlertStatus = (x: any): string =>
  (x?.alert?.status ?? x?.status ?? x?.alert_status ?? "") as string;

export const pickAlertScoreSnapshot = (x: any): number =>
  Number(x?.alert?.score_snapshot ?? x?.score_snapshot ?? 0);

export const pickAlertReason = (x: any): string =>
  (x?.alert?.reason ?? x?.reason ?? "") as string;

export const pickAlertCreatedAt = (x: any): string =>
  (x?.alert?.created_at ?? x?.created_at ?? "") as string;

export const pickTransaction = (x: any): Transaction | null =>
  (x?.transaction ?? null) as Transaction | null;

/**
 * pickTxAmount
 * - Retourne un montant numérique quel que soit le shape (nested/flat, string/number).
 *
 * ✅ Fallback :
 * - Si parsing impossible → 0 (évite NaN en UI).
 */
export const pickTxAmount = (x: any): number => {
  const raw = x?.transaction?.amount ?? x?.amount ?? 0;
  const n = typeof raw === "string" ? Number(raw) : Number(raw);
  return Number.isFinite(n) ? n : 0;
};

/**
 * pickTxDate
 * - Date d’occurrence tolérante :
 *   - backend: transaction.occurred_at
 *   - legacy: occurred_at / timestamp
 */
export const pickTxDate = (x: any): string => {
  return x?.transaction?.occurred_at ?? x?.occurred_at ?? x?.timestamp ?? "";
};
