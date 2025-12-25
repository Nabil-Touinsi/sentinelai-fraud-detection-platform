// frontend/pages/Simulator.tsx
import React, { useState } from "react";
import { Transaction, getCategoryColor, RiskLevel } from "../types";
import { ArrowRight, Play, Shield, AlertTriangle, CheckCircle } from "lucide-react";
import { apiFetch } from "../services/api";

/**
 * Page Simulator (Espace Démonstration)
 *
 * Rôle :
 * - Permet d’injecter des transactions “réelles” dans le backend (POST /transactions),
 *   puis de déclencher le scoring (POST /score).
 * - Objectif produit : montrer la réactivité du système et illustrer la différence
 *   entre un comportement “normal” et un cas “suspect”.
 *
 * Données / flux :
 * - 1) buildScenarioPayload() génère un payload cohérent (montant, merchant, zone, online…)
 * - 2) POST /transactions crée une transaction en base
 * - 3) POST /score calcule un score et peut créer une alerte si score >= threshold
 * - 4) On fusionne la réponse backend en un objet UI (Transaction + risk)
 *
 * Hypothèses importantes :
 * - Le backend accepte des champs simples (strings / number) pour éviter les erreurs de parsing.
 * - Le scoring renvoie :
 *   - score (0..100)
 *   - threshold (seuil d’alerte)
 *   - factors (explications)
 *
 * Règles produit :
 * - “Action Requise” si score >= threshold (niveau UI = "CRITIQUE")
 * - Sinon : niveau = LOW/MEDIUM/HIGH selon risk_level backend
 */

// Deux scénarios “métier”
type ScenarioType = "NORMAL" | "FRAUD";

type TxCreateResponse = {
  id: string;
  occurred_at: string;
  created_at: string;
  amount: string | number;
  currency: string;
  merchant_name: string;
  merchant_category: string;
  arrondissement: string;
  channel: string;
  is_online: boolean;
  description: string;
};

type ScoreResponse = {
  transaction_id: string;
  score: number;
  risk_level: string;
  factors: string[];
  threshold: number;
  alert: null | {
    id: string;
    status: string;
    score_snapshot: number;
    reason: string;
    created_at: string;
    updated_at: string;
  };
};

/**
 * TransactionWithRisk
 * - Type UI : on garde Transaction (types.ts) + on ajoute un bloc `risk` pour l’affichage.
 * - `level: "CRITIQUE"` est volontairement spécifique UI (déclenche “Action Requise”).
 */
type TransactionWithRisk = Transaction & {
  risk?: {
    score: number;
    level: "CRITIQUE" | RiskLevel | string;
    factors: string[];
  };
};

// ✅ une seule source de vérité: VITE_API_URL
const API_URL =
  (import.meta as any).env?.VITE_API_URL?.toString()?.replace(/\/+$/, "") ||
  "http://127.0.0.1:8000";

/**
 * isoNowPlusMinutes(deltaMinutes)
 * - Génère un ISO timestamp “crédible” autour de maintenant (jitter).
 * - Objectif : éviter des scénarios trop “figés” en démo.
 */
function isoNowPlusMinutes(deltaMinutes: number) {
  const d = new Date(Date.now() + deltaMinutes * 60 * 1000);
  return d.toISOString();
}

/** pick(arr) : tire un élément au hasard (variabilité de démo) */
function pick<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

/** rand(min, max) : nombre aléatoire uniforme */
function rand(min: number, max: number): number {
  return Math.random() * (max - min) + min;
}

/** chance(p) : true avec probabilité p */
function chance(p: number): boolean {
  return Math.random() < p;
}

/** round2(n) : arrondi à 2 décimales (montants crédibles) */
function round2(n: number): number {
  return Math.round(n * 100) / 100;
}

/**
 * buildScenarioPayload(type)
 * - Construit un payload NON statique mais cohérent avec l’intention :
 *   - NORMAL : petits montants, commerces “quotidiens”, online peu fréquent
 *   - FRAUD : montants élevés, ecommerce/électronique, online très fréquent
 *
 * ⚠️ Important :
 * - On conserve des valeurs “compatibles backend” (strings simples, catégories simples)
 * - Arrondissement : format "750xx" pour rester robuste si le backend parse ce champ
 */
function buildScenarioPayload(type: ScenarioType) {
  const normalMerchants = ["Carrefour City", "Monoprix", "Franprix", "Boulangerie", "SNCF", "Pharmacie"];
  const fraudMerchants = ["Amazon", "Cdiscount", "AliExpress", "Fnac.com", "Deliveroo", "Uber", "Apple Store"];

  const arrCodes = [
    "75001",
    "75002",
    "75003",
    "75004",
    "75005",
    "75006",
    "75007",
    "75008",
    "75009",
    "75010",
    "75011",
    "75012",
    "75013",
    "75014",
    "75015",
    "75016",
    "75017",
    "75018",
    "75019",
    "75020",
  ];

  const normalCategories = ["supermarche", "transport", "restaurant", "pharmacie", "shopping"];
  const fraudCategories = ["ecommerce", "electronics", "luxury", "giftcards", "services"];

  // Jitter : donne une impression “live” (transactions pas toutes à la même seconde)
  const jitterMinutes = Math.floor(rand(-180, 10)); // -3h à +10min
  const occurred_at = isoNowPlusMinutes(jitterMinutes);

  if (type === "FRAUD") {
    // Montant suspect : 300–3000€ + 5% d’extrême 7000–12000€
    let amount = rand(300, 3000);
    if (chance(0.05)) amount = rand(7000, 12000);

    const merchant_name = pick(fraudMerchants);
    const merchant_category = pick(fraudCategories);
    const arrondissement = pick(arrCodes);

    // Suspect = beaucoup plus souvent online
    const is_online = chance(0.85);

    const descriptions = [
      "achat en ligne montant élevé",
      "transaction ecommerce atypique",
      "paiement en ligne récurrent",
      "tentative achat rapide",
      "commande express montant élevé",
    ];

    return {
      occurred_at,
      amount: round2(amount),
      currency: "EUR",
      merchant_name,
      merchant_category,
      arrondissement,
      channel: "card",
      is_online,
      description: pick(descriptions),
    };
  }

  // NORMAL : 5–120€, mix online faible
  const amount = rand(5, 120);
  const merchant_name = pick(normalMerchants);
  const merchant_category = pick(normalCategories);
  const arrondissement = pick(arrCodes);
  const is_online = chance(0.25);

  const descriptions = ["achat quotidien", "paiement carte", "dépense courante", "achat alimentaire", "transport"];

  return {
    occurred_at,
    amount: round2(amount),
    currency: "EUR",
    merchant_name,
    merchant_category,
    arrondissement,
    channel: "card",
    is_online,
    description: pick(descriptions),
  };
}

/**
 * uiRiskLevelFromBackend(score, threshold, risk_level)
 * - Harmonise les libellés backend en un niveau UI :
 *   - si score >= threshold -> "CRITIQUE" (déclenche “Action Requise”)
 *   - sinon on mappe risk_level en LOW/MEDIUM/HIGH
 */
function uiRiskLevelFromBackend(score: number, threshold: number, risk_level: string) {
  if (score >= threshold) return "CRITIQUE";

  const r = (risk_level || "").toUpperCase();
  if (r.includes("HIGH")) return RiskLevel.HIGH;
  if (r.includes("MEDIUM")) return RiskLevel.MEDIUM;
  if (r.includes("LOW")) return RiskLevel.LOW;
  return RiskLevel.LOW;
}

/**
 * extractErrMsg(err)
 * - Rend un message d’erreur “présentable” (API / exception / objet).
 * - Objectif : feedback immédiat en démo sans exposer des stacktraces.
 */
function extractErrMsg(err: any): string {
  if (!err) return "Erreur inconnue";
  if (typeof err === "string") return err;
  if (err?.error?.message) return err.error.message;
  if (err?.message) return err.message;
  try {
    return JSON.stringify(err);
  } catch {
    return "Erreur inconnue";
  }
}

const Simulator = () => {
  const [loading, setLoading] = useState(false);
  const [lastTx, setLastTx] = useState<TransactionWithRisk | null>(null);
  const [error, setError] = useState<string | null>(null);

  /**
   * handleInject(type)
   * - Pipeline de démo :
   *   1) POST /transactions (création DB)
   *   2) POST /score (scoring + alerte éventuelle)
   *   3) Fusion en TransactionWithRisk pour affichage
   */
  const handleInject = async (type: ScenarioType) => {
    setLoading(true);
    setError(null);

    try {
      const txPayload = buildScenarioPayload(type);
      const tx = await apiFetch<TxCreateResponse>("/transactions", {
        method: "POST",
        body: JSON.stringify(txPayload),
      });

      const score = await apiFetch<ScoreResponse>("/score", {
        method: "POST",
        body: JSON.stringify({ transaction_id: tx.id }),
      });

      const merged: TransactionWithRisk = {
        ...(tx as Transaction),
        risk: {
          score: score.score,
          level: uiRiskLevelFromBackend(score.score, score.threshold, score.risk_level),
          factors: score.factors ?? [],
        },
      };

      setLastTx(merged);
    } catch (e: any) {
      console.error(e);
      setError(extractErrMsg(e));
      setLastTx(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8 py-6">
      <div className="text-center mb-10">
        <h1 className="text-3xl font-bold text-white tracking-tight mb-3">Espace Démonstration</h1>
        <p className="text-slate-400 text-lg max-w-2xl mx-auto">
          Testez la réactivité du système en simulant des transactions. Observez comment l&apos;outil distingue une
          opération standard d&apos;un comportement suspect.
        </p>
        <p className="text-xs text-slate-500 mt-3">
          Backend: <span className="text-slate-300">{API_URL}</span>
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Actions : 2 scénarios (normal vs suspect) */}
        <div className="space-y-4">
          <h2 className="text-sm font-bold text-slate-500 uppercase tracking-wider mb-4">Créer un scénario</h2>

          <button
            onClick={() => handleInject("NORMAL")}
            disabled={loading}
            className="w-full p-6 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded-xl flex items-center gap-4 transition-all group text-left"
          >
            <div className="w-12 h-12 rounded-full bg-emerald-500/10 flex items-center justify-center text-emerald-500 group-hover:bg-emerald-500 group-hover:text-white transition-colors">
              <Shield size={24} />
            </div>
            <div>
              <h3 className="text-white font-semibold text-lg">Exemple normal</h3>
              <p className="text-slate-500 text-sm">Achat quotidien (supermarché…), montant cohérent.</p>
            </div>
          </button>

          <button
            onClick={() => handleInject("FRAUD")}
            disabled={loading}
            className="w-full p-6 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded-xl flex items-center gap-4 transition-all group text-left"
          >
            <div className="w-12 h-12 rounded-full bg-red-500/10 flex items-center justify-center text-red-500 group-hover:bg-red-500 group-hover:text-white transition-colors">
              <AlertTriangle size={24} />
            </div>
            <div>
              <h3 className="text-white font-semibold text-lg">Exemple suspect</h3>
              <p className="text-slate-500 text-sm">Montant élevé + ecommerce/online → alerte attendue.</p>
            </div>
          </button>

          {error && (
            <div className="mt-2 p-3 rounded-lg border border-red-800 bg-red-950/40 text-red-200 text-sm">{error}</div>
          )}
        </div>

        {/* Résultat : une “carte” qui explique la décision */}
        <div className="bg-slate-950 border border-slate-800 rounded-xl p-6 relative min-h-[300px] flex flex-col">
          <h2 className="text-sm font-bold text-slate-500 uppercase tracking-wider mb-6">Résultat de l'analyse</h2>

          {loading ? (
            <div className="flex-1 flex flex-col items-center justify-center text-slate-500">
              <div className="animate-spin mb-4">
                <Play size={32} className="text-blue-500" />
              </div>
              <p>Création transaction + scoring...</p>
            </div>
          ) : lastTx ? (
            <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                  <div
                    className={`w-10 h-10 rounded-full flex items-center justify-center text-white font-bold ${getCategoryColor(
                      lastTx.merchant_category
                    )}`}
                  >
                    {lastTx.merchant_name?.charAt(0) ?? "T"}
                  </div>
                  <div>
                    <div className="text-white font-medium">{lastTx.merchant_name}</div>
                    <div className="text-xs text-slate-500">
                      {lastTx.merchant_category} • {lastTx.amount} €
                    </div>
                    <div className="text-[11px] text-slate-600 mt-1">
                      tx_id: <span className="text-slate-400">{lastTx.id}</span>
                    </div>
                  </div>
                </div>

                <div
                  className={`px-4 py-1.5 rounded-full text-sm font-bold border ${
                    lastTx.risk?.level === "CRITIQUE"
                      ? "bg-red-500 text-white border-red-600"
                      : "bg-emerald-500 text-white border-emerald-600"
                  }`}
                >
                  {lastTx.risk?.level === "CRITIQUE" ? "Action Requise" : "Validé"}
                </div>
              </div>

              <div className="space-y-6">
                <div>
                  <div className="flex justify-between text-sm mb-2">
                    <span className="text-slate-400">Niveau de risque calculé</span>
                    <span className="text-white font-bold">{lastTx.risk?.score ?? 0}/100</span>
                  </div>
                  <div className="h-3 w-full bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className={`h-full transition-all duration-1000 ${
                        (lastTx.risk?.score ?? 0) > 50 ? "bg-red-500" : "bg-emerald-500"
                      }`}
                      style={{ width: `${lastTx.risk?.score ?? 0}%` }}
                    />
                  </div>
                </div>

                <div className="bg-slate-900 rounded-lg p-4 border border-slate-800">
                  <span className="text-xs font-bold text-slate-500 uppercase mb-2 block">Explication du système</span>
                  {lastTx.risk?.factors?.length ? (
                    <ul className="space-y-2">
                      {lastTx.risk.factors.map((f, i) => (
                        <li key={i} className="text-sm text-red-300 flex items-start gap-2">
                          <ArrowRight size={16} className="mt-0.5 shrink-0" />
                          {f}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-sm text-emerald-400 flex items-center gap-2">
                      <CheckCircle size={16} />
                      Le comportement est cohérent.
                    </p>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-slate-600 border-2 border-dashed border-slate-800 rounded-lg bg-slate-900/30">
              <p>En attente d&apos;une simulation...</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Simulator;
