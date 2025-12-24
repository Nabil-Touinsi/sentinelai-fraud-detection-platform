// frontend/pages/Simulator.tsx
import React, { useState } from "react";
import { Transaction, getCategoryColor, RiskLevel } from "../types";
import { ArrowRight, Play, Shield, AlertTriangle, CheckCircle } from "lucide-react";
import { apiFetch } from "../services/api";

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

// ✅ Transaction backend + champ UI "risk"
type TransactionWithRisk = Transaction & {
  risk?: {
    score: number;
    level: "CRITIQUE" | RiskLevel | string;
    factors: string[];
  };
};

const API_URL =
  (import.meta as any).env?.VITE_API_URL?.toString()?.replace(/\/+$/, "") ||
  "http://127.0.0.1:8000";

function isoNowPlusMinutes(deltaMinutes: number) {
  const d = new Date(Date.now() + deltaMinutes * 60 * 1000);
  return d.toISOString();
}

function buildScenarioPayload(type: ScenarioType) {
  if (type === "FRAUD") {
    return {
      occurred_at: isoNowPlusMinutes(0),
      amount: 9999.99,
      currency: "EUR",
      merchant_name: "WS Test Extreme",
      merchant_category: "ecommerce",
      arrondissement: "75010",
      channel: "card",
      is_online: true,
      description: "test ws",
    };
  }

  return {
    occurred_at: isoNowPlusMinutes(0),
    amount: 24.9,
    currency: "EUR",
    merchant_name: "Carrefour City",
    merchant_category: "supermarche",
    arrondissement: "75011",
    channel: "card",
    is_online: false,
    description: "achat quotidien",
  };
}

function uiRiskLevelFromBackend(score: number, threshold: number, risk_level: string) {
  // Ton UI utilise "CRITIQUE" pour déclencher "Action Requise"
  if (score >= threshold) return "CRITIQUE";

  // Sinon on reste proche du backend
  const r = (risk_level || "").toUpperCase();
  if (r.includes("HIGH")) return RiskLevel.HIGH;
  if (r.includes("MEDIUM")) return RiskLevel.MEDIUM;
  if (r.includes("LOW")) return RiskLevel.LOW;
  return RiskLevel.LOW;
}

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

  const handleInject = async (type: ScenarioType) => {
    setLoading(true);
    setError(null);

    try {
      // 1) Crée une transaction réelle (DB)
      const txPayload = buildScenarioPayload(type);
      const tx = await apiFetch<TxCreateResponse>("/transactions", {
        method: "POST",
        body: JSON.stringify(txPayload),
      });

      // 2) Score la transaction (et crée une alerte si score >= threshold)
      const score = await apiFetch<ScoreResponse>("/score", {
        method: "POST",
        body: JSON.stringify({ transaction_id: tx.id }),
      });

      // 3) Merge en objet UI (Transaction + risk)
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
        {/* Actions */}
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

        {/* Result */}
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
