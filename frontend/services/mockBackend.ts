// frontend/services/mockBackend.ts
import { Transaction, RiskScore, Alert, AlertStatus } from '../types';

/**
 * MockBackend = fallback / démo locale
 * Aligné avec types.ts (backend models):
 * - Transaction : occurred_at, amount, currency, merchant_name, merchant_category, arrondissement, channel, is_online, description?
 * - RiskScore   : id, transaction_id, score, model_version, created_at
 * - Alert       : id, transaction_id, risk_score_id?, score_snapshot, status, reason, created_at, updated_at, comment?, handler_name?
 *
 * ⚠️ Note: on ajoute des champs "extra" côté mock (risk.factors, transaction.zone_paris, etc.)
 * pour nourrir l'UI sans casser les types (l’UI les consomme en `any`).
 */

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

const THRESHOLD = 70; // seuil alerte mock

const MERCHANTS = [
  { cat: 'ecommerce', names: ['Amazon FR', 'Cdiscount', 'Fnac.com', 'Vinted', 'Leboncoin'], avg: 60 },
  { cat: 'electronics', names: ['Apple Store', 'Boulanger', 'Darty', 'Fnac', 'LDLC'], avg: 350 },
  { cat: 'food', names: ['Carrefour City', 'Monoprix', 'Franprix', 'Auchan'], avg: 35 },
  { cat: 'transport', names: ['SNCF Connect', 'RATP', 'Uber', 'Bolt'], avg: 25 },
  { cat: 'hotel', names: ['Accor Hotels', 'Ibis Styles', 'Novotel', 'Hilton'], avg: 220 },
  { cat: 'luxury', names: ['Louis Vuitton', 'Gucci', 'Hermès', 'Chanel'], avg: 1500 },
];

const rand = (min: number, max: number) => Math.floor(Math.random() * (max - min + 1)) + min;
const pick = <T,>(arr: T[]): T => arr[Math.floor(Math.random() * arr.length)];
const nowIso = () => new Date().toISOString();

const makeId = (prefix: string) => `${prefix}_${Math.random().toString(36).slice(2, 10)}_${Date.now().toString(36)}`;

type RiskMeta = {
  factors: string[];
};

let transactions: Transaction[] = [];
let riskScoresByTx: Record<string, RiskScore> = {};
let riskMetaByTx: Record<string, RiskMeta> = {};
let alerts: Alert[] = [];

/** Génère une tx "backend-like" */
function buildTx(kind: 'NORMAL' | 'FRAUD'): Transaction & { zone_paris?: number } {
  const base = pick(MERCHANTS);

  let cat = base.cat;
  let merchant_name = pick(base.names);
  let amount = Number((base.avg * (0.7 + Math.random() * 0.8)).toFixed(2));
  let is_online = Math.random() < 0.4;

  // “fraud” = montant plus élevé + online + catégories à risque
  if (kind === 'FRAUD') {
    const fraudCat = pick(['ecommerce', 'electronics', 'luxury']);
    const m = MERCHANTS.find((x) => x.cat === fraudCat) ?? base;
    cat = m.cat;
    merchant_name = pick(m.names);

    if (cat === 'luxury') amount = Number((m.avg * (0.9 + Math.random() * 0.8)).toFixed(2));
    else if (cat === 'electronics') amount = 2599.99;
    else amount = 9999.99;

    is_online = true;
  }

  const tx: Transaction & { zone_paris?: number } = {
    id: makeId('tx'),
    occurred_at: nowIso(),
    amount,
    currency: 'EUR',
    merchant_name,
    merchant_category: cat,
    arrondissement: String(rand(1, 20)).padStart(2, '0'), // "01".."20" (mock)
    channel: 'card',
    is_online,
    description: kind === 'FRAUD' ? 'scenario suspect (mock)' : 'scenario normal (mock)',

    // extras UI (dashboard affiche parfois zone_paris)
    zone_paris: rand(1, 20),
  };

  return tx;
}

function computeRisk(tx: Transaction & { zone_paris?: number }): { score: number; factors: string[]; reason: string } {
  const factors: string[] = [];
  let score = 0;

  const amt = typeof tx.amount === 'string' ? Number(tx.amount) : tx.amount;

  // 1) online
  if (tx.is_online) {
    score += 18;
    factors.push('Transaction en ligne');
  }

  // 2) montant
  if (amt >= 2000) {
    score += 45;
    factors.push('Montant très élevé (>= 2000€)');
  } else if (amt >= 500) {
    score += 25;
    factors.push('Montant élevé (>= 500€)');
  } else if (amt >= 200) {
    score += 12;
    factors.push('Montant au-dessus de la moyenne');
  }

  // 3) catégorie à risque
  const cat = (tx.merchant_category || '').toLowerCase();
  if (['luxury', 'electronics', 'ecommerce'].includes(cat)) {
    score += 20;
    factors.push(`Catégorie à risque (${cat})`);
  }

  // 4) “fréquence” fake: si déjà plusieurs tx mêmes cat, on augmente
  const sameCatRecent = transactions.slice(0, 15).filter((t) => (t.merchant_category || '').toLowerCase() === cat).length;
  if (sameCatRecent >= 3) {
    score += 10;
    factors.push(`Fréquence modérée (>= 3 transactions récentes en ${cat})`);
  }

  // 5) bruit
  score += rand(0, 6);
  score = Math.max(0, Math.min(100, score));

  const reason = score >= THRESHOLD ? 'Score élevé détecté (mock)' : 'Comportement cohérent (mock)';
  return { score, factors, reason };
}

function ingest(kind: 'NORMAL' | 'FRAUD') {
  const tx = buildTx(kind);
  const { score, factors, reason } = computeRisk(tx);

  const riskScore: RiskScore = {
    id: makeId('rs'),
    transaction_id: tx.id,
    score,
    model_version: score >= 50 ? 'xgboost_mock' : 'iforest_mock',
    created_at: nowIso(),
  };

  riskScoresByTx[tx.id] = riskScore;
  riskMetaByTx[tx.id] = { factors };

  // insert tx au début
  transactions.unshift(tx);

  let createdAlert: Alert | null = null;

  if (score >= THRESHOLD) {
    createdAlert = {
      id: makeId('al'),
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

function seedIfEmpty() {
  if (transactions.length > 0) return;

  // 8 normales + 3 fraud
  for (let i = 0; i < 8; i++) ingest('NORMAL');
  for (let i = 0; i < 3; i++) ingest('FRAUD');
}

export const MockBackend = {
  /** optionnel: pratique si un écran legacy l'appelle encore */
  generateScenario: async (type: 'NORMAL' | 'FRAUD') => {
    seedIfEmpty();
    await sleep(350);
    return ingest(type);
  },

  /** utile si une page transactions legacy existe encore */
  getTransactions: async () => {
    seedIfEmpty();
    await sleep(200);

    // retourne un shape enrichi (transaction + risk + alert) comme les UIs aiment bien
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

  /** utilisé par Dashboard.tsx (dans ton code actuel) */
  getAlerts: async (): Promise<any[]> => {
    seedIfEmpty();
    await sleep(200);

    // Dashboard consomme: alert.transaction + alert.risk.factors + alert.status + created_at + score_snapshot
    return alerts.map((a) => {
      const tx = transactions.find((t) => t.id === a.transaction_id)!;
      const rs = riskScoresByTx[a.transaction_id];

      return {
        ...a,
        transaction: tx,
        // champ "risk" (extra) pour afficher factors facilement (Dashboard lit alert.risk?.factors?.[0])
        risk: {
          score: rs?.score ?? a.score_snapshot ?? 0,
          factors: riskMetaByTx[a.transaction_id]?.factors ?? [],
        },
      };
    });
  },

  /** utilisé par Dashboard.tsx */
  getStats: async () => {
    seedIfEmpty();
    await sleep(150);

    const openAlerts = alerts.filter((a) => String(a.status).toUpperCase() !== AlertStatus.CLOTURE).length;
    const criticalAlerts = alerts.filter((a) => (a.score_snapshot ?? 0) >= 85 && String(a.status).toUpperCase() !== AlertStatus.CLOTURE).length;

    return {
      totalTransactionsToday: transactions.length,
      openAlerts,
      criticalAlerts,
      avgResolutionTimeMinutes: 24,
    };
  },

  /** pratique si une UI permet de changer le statut */
  updateAlertStatus: async (id: string, status: AlertStatus, comment?: string) => {
    await sleep(120);
    const a = alerts.find((x) => x.id === id);
    if (!a) return;

    a.status = status;
    a.updated_at = nowIso();
    if (comment) a.comment = comment;
  },
};
