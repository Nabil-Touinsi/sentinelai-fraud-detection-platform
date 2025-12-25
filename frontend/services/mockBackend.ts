// frontend/services/mockBackend.ts
import { Transaction, RiskScore, Alert, AlertStatus } from "../types";

/**
 * MockBackend (fallback / démo locale)
 *
 * Rôle :
 * - Simuler un backend “crédible” quand l’API n’est pas dispo (offline, démo, dev rapide).
 * - Produire des objets proches du backend (Transaction / RiskScore / Alert),
 *   tout en ajoutant quelques champs “UI-friendly” (risk.factors, zone_paris…).
 *
 * Données manipulées :
 * - Transaction :
 *   - occurred_at, amount, currency, merchant_name, merchant_category, arrondissement, channel, is_online, description
 * - RiskScore :
 *   - score (0..100), model_version, created_at
 * - Alert :
 *   - score_snapshot, status (A_TRAITER / EN_ENQUETE / CLOTURE), reason, created_at, updated_at
 *
 * Sorties principales :
 * - generateScenario(type) : crée une transaction + scoring + alerte éventuelle
 * - getTransactions() : liste enrichie pour l’UI (transaction + risk_score + risk + alert)
 * - getAlerts() : shape attendu par Dashboard (alert + transaction + risk{factors})
 * - getStats() : KPIs simples (à usage dashboard legacy)
 *
 * Hypothèses importantes :
 * - THRESHOLD (70) détermine la création d’une alerte.
 * - Les listes sont en mémoire (refresh page = reset).
 *
 * ⚠️ Champs “extra” :
 * - zone_paris, risk.factors… ne sont pas des champs backend stricts.
 * - L’UI les consomme souvent via `any` pour rester compatible.
 */

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Seuil de création d’alerte dans le mock (aligné sur l’idée “score >= seuil => alerte”) */
const THRESHOLD = 70;

const MERCHANTS = [
  { cat: "ecommerce", names: ["Amazon FR", "Cdiscount", "Fnac.com", "Vinted", "Leboncoin"], avg: 60 },
  { cat: "electronics", names: ["Apple Store", "Boulanger", "Darty", "Fnac", "LDLC"], avg: 350 },
  { cat: "food", names: ["Carrefour City", "Monoprix", "Franprix", "Auchan"], avg: 35 },
  { cat: "transport", names: ["SNCF Connect", "RATP", "Uber", "Bolt"], avg: 25 },
  { cat: "hotel", names: ["Accor Hotels", "Ibis Styles", "Novotel", "Hilton"], avg: 220 },
  { cat: "luxury", names: ["Louis Vuitton", "Gucci", "Hermès", "Chanel"], avg: 1500 },
];

/**
 * Helpers “random”
 * - Ici, le hasard sert à rendre la démo moins répétitive.
 * - Les bornes sont volontairement simples pour garder un contrôle sur les valeurs.
 */
const rand = (min: number, max: number) => Math.floor(Math.random() * (max - min + 1)) + min;
const pick = <T,>(arr: T[]): T => arr[Math.floor(Math.random() * arr.length)];
const nowIso = () => new Date().toISOString();

const makeId = (prefix: string) => `${prefix}_${Math.random().toString(36).slice(2, 10)}_${Date.now().toString(36)}`;

type RiskMeta = {
  factors: string[];
};

/**
 * “Base de données” en mémoire
 * - transactions : flux global (on unshift pour mettre les plus récentes en premier)
 * - riskScoresByTx : map tx.id -> RiskScore
 * - riskMetaByTx : map tx.id -> facteurs (pour UI)
 * - alerts : alertes actives / historiques (on unshift aussi)
 */
let transactions: Transaction[] = [];
let riskScoresByTx: Record<string, RiskScore> = {};
let riskMetaByTx: Record<string, RiskMeta> = {};
let alerts: Alert[] = [];

/**
 * buildTx(kind)
 * - Génère une transaction “backend-like”.
 *
 * Règle produit simulée :
 * - NORMAL : montants modestes, online pas systématique
 * - FRAUD  : montants élevés, souvent online, catégories à risque
 *
 * ⚠️ arrondissement :
 * - Ici c’est "01".."20" (mock). Certaines pages préfèrent "750xx".
 * - On ajoute zone_paris (1..20) pour les composants type ParisMap.
 */
function buildTx(kind: "NORMAL" | "FRAUD"): Transaction & { zone_paris?: number } {
  const base = pick(MERCHANTS);

  let cat = base.cat;
  let merchant_name = pick(base.names);
  let amount = Number((base.avg * (0.7 + Math.random() * 0.8)).toFixed(2));
  let is_online = Math.random() < 0.4;

  // ✅ FRAUD : forcer un pattern très “lisible” en UI (démo)
  if (kind === "FRAUD") {
    const fraudCat = pick(["ecommerce", "electronics", "luxury"]);
    const m = MERCHANTS.find((x) => x.cat === fraudCat) ?? base;
    cat = m.cat;
    merchant_name = pick(m.names);

    if (cat === "luxury") amount = Number((m.avg * (0.9 + Math.random() * 0.8)).toFixed(2));
    else if (cat === "electronics") amount = 2599.99;
    else amount = 9999.99;

    is_online = true;
  }

  const tx: Transaction & { zone_paris?: number } = {
    id: makeId("tx"),
    occurred_at: nowIso(),
    amount,
    currency: "EUR",
    merchant_name,
    merchant_category: cat,
    arrondissement: String(rand(1, 20)).padStart(2, "0"), // "01".."20" (mock)
    channel: "card",
    is_online,
    description: kind === "FRAUD" ? "scenario suspect (mock)" : "scenario normal (mock)",

    // ✅ extra UI : utile pour ParisMap / tiles
    zone_paris: rand(1, 20),
  };

  return tx;
}

/**
 * computeRisk(tx)
 * - Calcule un score (0..100) + des facteurs lisibles.
 *
 * Pourquoi ces règles ?
 * - L’objectif n’est pas la précision statistique, mais la pédagogie :
 *   l’UI doit voir “pourquoi” un score monte (online, montant, catégorie, répétition…).
 *
 * ✅ Score final :
 * - borné à [0..100]
 * - ajoute un “bruit” léger pour éviter des valeurs identiques
 */
function computeRisk(
  tx: Transaction & { zone_paris?: number }
): { score: number; factors: string[]; reason: string } {
  const factors: string[] = [];
  let score = 0;

  const amt = typeof tx.amount === "string" ? Number(tx.amount) : tx.amount;

  /** 1) Online : signal simple, souvent associé à des patterns frauduleux en démo */
  if (tx.is_online) {
    score += 18;
    factors.push("Transaction en ligne");
  }

  /** 2) Montant : escalade par paliers (plus lisible qu’une formule continue) */
  if (amt >= 2000) {
    score += 45;
    factors.push("Montant très élevé (>= 2000€)");
  } else if (amt >= 500) {
    score += 25;
    factors.push("Montant élevé (>= 500€)");
  } else if (amt >= 200) {
    score += 12;
    factors.push("Montant au-dessus de la moyenne");
  }

  /** 3) Catégorie : quelques catégories “à risque” pour rendre la démo cohérente */
  const cat = (tx.merchant_category || "").toLowerCase();
  if (["luxury", "electronics", "ecommerce"].includes(cat)) {
    score += 20;
    factors.push(`Catégorie à risque (${cat})`);
  }

  /**
   * 4) “Fréquence” (simulée)
   * - On regarde les 15 dernières tx pour créer un effet “répétition”.
   * - Permet de montrer des facteurs non liés au seul montant.
   */
  const sameCatRecent = transactions
    .slice(0, 15)
    .filter((t) => (t.merchant_category || "").toLowerCase() === cat).length;

  if (sameCatRecent >= 3) {
    score += 10;
    factors.push(`Fréquence modérée (>= 3 transactions récentes en ${cat})`);
  }

  /** 5) Bruit : petite variation (évite d’avoir toujours les mêmes scores) */
  score += rand(0, 6);
  score = Math.max(0, Math.min(100, score));

  const reason = score >= THRESHOLD ? "Score élevé détecté (mock)" : "Comportement cohérent (mock)";
  return { score, factors, reason };
}

/**
 * ingest(kind)
 * - Pipeline complet :
 *   1) buildTx
 *   2) computeRisk
 *   3) create RiskScore
 *   4) create Alert si score >= THRESHOLD
 *
 * ✅ Important : insertion en tête
 * - L’UI affiche généralement “les plus récents en premier”.
 */
function ingest(kind: "NORMAL" | "FRAUD") {
  const tx = buildTx(kind);
  const { score, factors, reason } = computeRisk(tx);

  const riskScore: RiskScore = {
    id: makeId("rs"),
    transaction_id: tx.id,
    score,
    model_version: score >= 50 ? "xgboost_mock" : "iforest_mock",
    created_at: nowIso(),
  };

  riskScoresByTx[tx.id] = riskScore;
  riskMetaByTx[tx.id] = { factors };

  // ✅ insert tx au début
  transactions.unshift(tx);

  let createdAlert: Alert | null = null;

  if (score >= THRESHOLD) {
    createdAlert = {
      id: makeId("al"),
      transaction_id: tx.id,
      risk_score_id: riskScore.id,
      score_snapshot: score,
      status: AlertStatus.A_TRAITER,
      reason,
      created_at: nowIso(),
      updated_at: nowIso(),
    };
    alerts.unshift(createdAlert);
  }

  return { tx, riskScore, createdAlert };
}

/**
 * seedIfEmpty()
 * - Pré-remplit le mock au premier appel pour que l’app ait “du contenu”.
 * - Répartition : majorité de NORMAL + quelques FRAUD pour montrer des alertes.
 */
function seedIfEmpty() {
  if (transactions.length > 0) return;

  // 8 normales + 3 fraud
  for (let i = 0; i < 8; i++) ingest("NORMAL");
  for (let i = 0; i < 3; i++) ingest("FRAUD");
}

export const MockBackend = {
  /**
   * generateScenario(type)
   * - API “legacy” : certains écrans l’utilisent encore (démo injectée).
   */
  generateScenario: async (type: "NORMAL" | "FRAUD") => {
    seedIfEmpty();
    await sleep(350);
    return ingest(type);
  },

  /**
   * getTransactions()
   * - Retourne un shape enrichi pensé pour l’UI :
   *   - transaction
   *   - risk_score (objet type backend)
   *   - risk (extra UI) : score + factors
   *   - alert éventuelle
   *
   * Pourquoi enrichir ?
   * - Simplifie les pages qui veulent tout afficher sans recroiser 3 sources.
   */
  getTransactions: async () => {
    seedIfEmpty();
    await sleep(200);

    return transactions.map((t) => ({
      transaction: t,
      risk_score: riskScoresByTx[t.id],
      risk: {
        score: riskScoresByTx[t.id]?.score ?? 0,
        factors: riskMetaByTx[t.id]?.factors ?? [],
      },
      alert: alerts.find((a) => a.transaction_id === t.id) ?? null,
    }));
  },

  /**
   * getAlerts()
   * - Dashboard consomme : alert + transaction + risk.factors (pour afficher la raison courte).
   * - On reconstruit donc un objet compatible “dashboard-friendly”.
   */
  getAlerts: async (): Promise<any[]> => {
    seedIfEmpty();
    await sleep(200);

    return alerts.map((a) => {
      const tx = transactions.find((t) => t.id === a.transaction_id)!;
      const rs = riskScoresByTx[a.transaction_id];

      return {
        ...a,
        transaction: tx,
        // ✅ extra UI : facilite l’affichage “raison/factors” sans aller chercher ailleurs
        risk: {
          score: rs?.score ?? a.score_snapshot ?? 0,
          factors: riskMetaByTx[a.transaction_id]?.factors ?? [],
        },
      };
    });
  },

  /**
   * getStats()
   * - KPIs simples pour un dashboard legacy.
   * - ⚠️ Valeurs "démo" : avgResolutionTimeMinutes est fixe ici.
   */
  getStats: async () => {
    seedIfEmpty();
    await sleep(150);

    const openAlerts = alerts.filter((a) => String(a.status).toUpperCase() !== AlertStatus.CLOTURE).length;
    const criticalAlerts = alerts.filter(
      (a) => (a.score_snapshot ?? 0) >= 85 && String(a.status).toUpperCase() !== AlertStatus.CLOTURE
    ).length;

    return {
      totalTransactionsToday: transactions.length,
      openAlerts,
      criticalAlerts,
      avgResolutionTimeMinutes: 24,
    };
  },

  /**
   * updateAlertStatus(id, status, comment?)
   * - Simule une action opérateur (mettre en enquête / clôturer).
   * - ✅ Met à jour updated_at pour refléter un “traitement”.
   */
  updateAlertStatus: async (id: string, status: AlertStatus, comment?: string) => {
    await sleep(120);
    const a = alerts.find((x) => x.id === id);
    if (!a) return;

    a.status = status;
    a.updated_at = nowIso();
    if (comment) a.comment = comment;
  },
};
