// frontend/pages/Transactions.tsx
import React, { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../services/api";
import type { Transaction, RiskScore, Alert } from "../types";
import { RiskLevel, getRiskLabel, getRiskColor, getCategoryColor } from "../types";
import { explainRiskWithGemini } from "../services/gemini";
import { X, ChevronRight, Bot, Check, AlertCircle, CreditCard, Smartphone, Globe } from "lucide-react";

/**
 * Page Transactions
 *
 * Rôle :
 * - Affiche une liste paginée (côté backend) des transactions récentes.
 * - Permet de filtrer rapidement (Tout / Cas urgents / À vérifier).
 * - Ouvre un panneau de détail (slide-over) pour analyser une transaction :
 *   - score + niveau (LOW/MEDIUM/HIGH)
 *   - facteurs (si disponibles)
 *   - statut “Signalé” si une alerte existe
 * - Optionnel : demander une explication “pédagogique” via l’assistant (Gemini).
 *
 * Données attendues (backend) :
 * - GET /transactions?page=&page_size=
 *   -> { data: TransactionListItem[], meta: { page, page_size, total } }
 * - Chaque item peut contenir :
 *   - transaction (obligatoire)
 *   - risk_score (optionnel) : score “officiel” (prioritaire)
 *   - alert (optionnel) : si la transaction a déclenché un dossier
 *   - risk (optionnel) : compat legacy / mock (score + facteurs)
 *
 * Hypothèses importantes :
 * - Le score est attendu en 0..100.
 * - Le backend limite page_size à 100 → on “précharge” 2 pages pour viser ~200 lignes.
 *
 * Règles produit :
 * - Cas urgents : score >= 80
 * - À vérifier : score >= 50 et < 80
 * - OK : score < 50
 */

type TransactionListItem = {
  transaction: Transaction;
  risk_score?: RiskScore | null;
  alert?: Alert | null;

  // Optionnel (si un jour tu enrichis côté backend / mock)
  risk?: { score?: number; factors?: string[] };
};

type TransactionListResponse = {
  data: TransactionListItem[];
  meta: { page: number; page_size: number; total: number };
};

/** Seuils UI (simple et lisible) */
const SUSPICIOUS_MEDIUM = 50;
const SUSPICIOUS_HIGH = 80;

// backend: page_size max = 100 (FastAPI Query(le=100))
const PAGE_SIZE_MAX = 100;
// si tu veux ~200 lignes, on fetch 2 pages
const DEFAULT_LIMIT = 200;

/**
 * computeRiskLevel(score)
 * - Traduit un score (0..100) en 3 niveaux UI.
 * - Utilisé pour : couleur, libellé, filtre et CTA.
 */
function computeRiskLevel(score: number): RiskLevel {
  if (score >= SUSPICIOUS_HIGH) return RiskLevel.HIGH;
  if (score >= SUSPICIOUS_MEDIUM) return RiskLevel.MEDIUM;
  return RiskLevel.LOW;
}

/**
 * safeNumber(x)
 * - Normalise une valeur (string|number|autre) en number.
 * - ✅ Évite les NaN en UI (montants, scores).
 */
function safeNumber(x: unknown, fallback = 0): number {
  const n = typeof x === "string" ? Number(x) : typeof x === "number" ? x : NaN;
  return Number.isFinite(n) ? n : fallback;
}

/**
 * pickScore(item)
 * - ✅ Source de vérité : risk_score.score si présent (valeur backend “officielle”)
 * - Fallback : item.risk.score (compat legacy / mock)
 */
function pickScore(item: TransactionListItem): number {
  const fromRiskScore = safeNumber(item?.risk_score?.score, NaN);
  if (Number.isFinite(fromRiskScore)) return fromRiskScore;
  return safeNumber(item?.risk?.score, 0);
}

/**
 * pickFactors(item)
 * - Facteurs uniquement si la structure legacy `risk.factors` existe.
 * - Le backend actuel peut ne pas fournir de facteurs sur /transactions.
 */
function pickFactors(item: TransactionListItem): string[] {
  const f = item?.risk?.factors;
  return Array.isArray(f) ? f : [];
}

/**
 * getPaymentLabel(item)
 * - Traduit les champs transaction en un libellé UI simple.
 * - Objectif : lecture rapide dans la table + détail.
 */
function getPaymentLabel(item: TransactionListItem): string {
  const tx = item.transaction;
  if (tx.is_online) return "En ligne";
  const ch = (tx.channel || "").toLowerCase();
  if (ch.includes("mobile")) return "Mobile";
  if (ch.includes("card")) return "Carte";
  return tx.channel || "Paiement";
}

/**
 * getPaymentIcon(label)
 * - Associe un pictogramme au libellé (repère visuel).
 */
function getPaymentIcon(label: string) {
  if (label === "En ligne") return <Globe size={12} />;
  if (["Apple Pay", "Sans Contact", "Google Pay", "Mobile"].includes(label)) return <Smartphone size={12} />;
  return <CreditCard size={12} />;
}

/**
 * extractErrMsg(err)
 * - Rend les erreurs API “présentables” (bannière UI).
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

/**
 * fetchFirstNTransactions(n)
 * - Récupère n transactions en paginant côté backend (page_size limité à 100).
 *
 * Pourquoi ce choix ?
 * - On veut un tableau “dense” pour la démo (ex: 200 lignes) sans ajouter de pagination UI.
 * - ⚠️ On évite d’envoyer sort_by/order tant qu’on n’a pas garanti leur support backend.
 */
async function fetchFirstNTransactions(n = DEFAULT_LIMIT): Promise<TransactionListItem[]> {
  const pageSize = PAGE_SIZE_MAX;
  let page = 1;
  let all: TransactionListItem[] = [];
  let total = Infinity;

  while (all.length < n && all.length < total) {
    const res = await apiFetch<TransactionListResponse>(`/transactions?page=${page}&page_size=${pageSize}`);

    const batch = res.data ?? [];
    total = res.meta?.total ?? all.length + batch.length;

    all = all.concat(batch);
    if (batch.length === 0) break;
    page += 1;
  }

  return all.slice(0, n);
}

const Transactions = () => {
  const [transactions, setTransactions] = useState<TransactionListItem[]>([]);
  const [selectedTx, setSelectedTx] = useState<TransactionListItem | null>(null);
  const [filter, setFilter] = useState<"ALL" | "HIGH" | "CHECK">("ALL");

  // États UI (chargement / erreur)
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Assistant IA (explication pédagogique)
  const [aiAnalysis, setAiAnalysis] = useState("");
  const [analyzing, setAnalyzing] = useState(false);

  /**
   * fetchTransactions()
   * - Charge la liste initiale (≈200 lignes).
   * - Sert aussi de “refresh” après une action (ex: patch d’alerte).
   */
  const fetchTransactions = async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const items = await fetchFirstNTransactions(DEFAULT_LIMIT);
      setTransactions(items);
    } catch (e: any) {
      setLoadError(extractErrMsg(e));
      setTransactions([]);
    } finally {
      setLoading(false);
    }
  };

  // Initial load
  useEffect(() => {
    fetchTransactions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /**
   * filtered
   * - Filtre UI instantané basé sur le score (sans refetch).
   * - “Cas urgents” = HIGH, “À vérifier” = MEDIUM.
   */
  const filtered = useMemo(() => {
    return transactions.filter((t) => {
      const score = pickScore(t);
      const level = computeRiskLevel(score);
      if (filter === "HIGH") return level === RiskLevel.HIGH;
      if (filter === "CHECK") return level === RiskLevel.MEDIUM;
      return true;
    });
  }, [transactions, filter]);

  const handleRowClick = (tx: TransactionListItem) => {
    setSelectedTx(tx);
    setAiAnalysis("");
  };

  /**
   * handleAnalyze()
   * - Appelle un service externe (Gemini) pour produire une explication pédagogique.
   * - ✅ On conserve le “payload legacy” sans casser l’intégration existante.
   */
  const handleAnalyze = async () => {
    if (!selectedTx) return;
    setAnalyzing(true);

    const score = pickScore(selectedTx);
    const level = computeRiskLevel(score);
    const paymentLabel = getPaymentLabel(selectedTx);

    const legacyPayload = {
      id: selectedTx.transaction.id,
      amount: selectedTx.transaction.amount,
      currency: selectedTx.transaction.currency,
      merchant_name: selectedTx.transaction.merchant_name,
      merchant_category: selectedTx.transaction.merchant_category,
      zone_paris: selectedTx.transaction.arrondissement,
      payment_method: paymentLabel,
      timestamp: selectedTx.transaction.occurred_at,
      risk: {
        score,
        level,
        factors: pickFactors(selectedTx),
      },
      alert: selectedTx.alert ?? null,
    };

    try {
      const text = await explainRiskWithGemini(legacyPayload as any);
      setAiAnalysis(text);
    } finally {
      setAnalyzing(false);
    }
  };

  /**
   * patchAlertStatus(status, comment)
   * - Permet d’agir sur le dossier lié à la transaction (si alert existe).
   * - ✅ Règle backend : un comment est requis à la clôture.
   * - Après patch : on refresh la liste pour rester aligné backend.
   */
  const patchAlertStatus = async (status: "EN_ENQUETE" | "CLOTURE", comment: string) => {
    if (!selectedTx?.alert) return;

    const safeComment = status === "CLOTURE" ? (comment || "").trim() || "Clôture via UI" : (comment || "").trim();

    await apiFetch(
      `/alerts/${selectedTx.alert.id}`,
      {
        method: "PATCH",
        body: JSON.stringify({ status, comment: safeComment }),
      },
      { auth: true }
    );

    await fetchTransactions();
    setSelectedTx(null);
  };

  return (
    <div className="relative h-[calc(100vh-100px)] flex flex-col">
      {/* En-tête + filtres rapides */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white tracking-tight">Transactions récentes</h1>
        <p className="text-slate-400 text-sm mb-4">Historique des flux pour analyse et contrôle.</p>

        {/* ✅ Bannière de chargement / erreur (feedback immédiat) */}
        <div className="mb-4 flex items-center gap-3">
          {loading && (
            <div className="text-xs px-3 py-2 rounded-lg border border-slate-800 bg-slate-900/50 text-slate-300">
              Chargement…
            </div>
          )}
          {loadError && (
            <div className="flex-1 text-xs px-3 py-2 rounded-lg border border-red-500/20 bg-red-500/10 text-red-200">
              {loadError}
              <button onClick={fetchTransactions} className="ml-3 underline text-red-100 hover:text-white">
                Réessayer
              </button>
            </div>
          )}
        </div>

        {/* Filtres : lecture métier (urgents / à vérifier) */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setFilter("ALL")}
            className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
              filter === "ALL"
                ? "bg-slate-700 text-white border-slate-600"
                : "bg-transparent text-slate-500 border-slate-800 hover:border-slate-600"
            }`}
          >
            Tout voir
          </button>
          <button
            onClick={() => setFilter("HIGH")}
            className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
              filter === "HIGH"
                ? "bg-red-500/10 text-red-400 border-red-500/20"
                : "bg-transparent text-slate-500 border-slate-800 hover:border-slate-600"
            }`}
          >
            Cas Urgents
          </button>
          <button
            onClick={() => setFilter("CHECK")}
            className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
              filter === "CHECK"
                ? "bg-amber-500/10 text-amber-400 border-amber-500/20"
                : "bg-transparent text-slate-500 border-slate-800 hover:border-slate-600"
            }`}
          >
            À vérifier
          </button>
        </div>
      </div>

      {/* Table : liste principale */}
      <div className="flex-1 overflow-auto bg-slate-900 border border-slate-800 rounded-xl relative shadow-sm">
        <table className="w-full text-left text-sm text-slate-400">
          <thead className="bg-slate-950 text-slate-300 font-semibold sticky top-0 z-10">
            <tr>
              <th className="p-4 border-b border-slate-800 w-32">Heure</th>
              <th className="p-4 border-b border-slate-800">Commerçant</th>
              <th className="p-4 border-b border-slate-800 text-right">Montant</th>
              <th className="p-4 border-b border-slate-800 w-48">Risque</th>
              <th className="p-4 border-b border-slate-800 w-32">Statut</th>
              <th className="p-4 border-b border-slate-800 w-10"></th>
            </tr>
          </thead>

          <tbody className="divide-y divide-slate-800">
            {filtered.map((item) => {
              const tx = item.transaction;

              const score = pickScore(item);
              const level = computeRiskLevel(score);
              const riskColor = getRiskColor(level);

              const amount = safeNumber(tx.amount, 0);
              const paymentLabel = getPaymentLabel(item);

              return (
                <tr
                  key={tx.id}
                  onClick={() => handleRowClick(item)}
                  className={`cursor-pointer transition-colors group ${
                    selectedTx?.transaction.id === tx.id ? "bg-blue-900/10" : "hover:bg-slate-800/50"
                  }`}
                >
                  <td className="p-4 font-mono text-xs">
                    {tx.occurred_at ? new Date(tx.occurred_at).toLocaleTimeString() : "—"}
                  </td>

                  <td className="p-4">
                    <div className="flex items-center gap-3">
                      <div
                        className={`w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold ${getCategoryColor(
                          tx.merchant_category
                        )}`}
                      >
                        {(tx.merchant_name || "?").charAt(0)}
                      </div>
                      <div>
                        <div className="text-slate-200 font-medium">{tx.merchant_name}</div>
                        <div className="text-xs text-slate-500 flex items-center gap-1.5">
                          {tx.merchant_category} • {tx.arrondissement}
                        </div>
                      </div>
                    </div>
                  </td>

                  <td className="p-4 text-right">
                    <div className="font-mono text-slate-200 font-medium">{amount.toFixed(2)} €</div>
                    <div className="text-[10px] text-slate-500 flex items-center justify-end gap-1 mt-0.5">
                      {getPaymentIcon(paymentLabel)} {paymentLabel}
                    </div>
                  </td>

                  <td className="p-4">
                    <span
                      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${riskColor}`}
                    >
                      {score}/100 • {getRiskLabel(level)}
                    </span>
                  </td>

                  <td className="p-4">
                    {item.alert ? (
                      <span className="text-xs text-slate-400 flex items-center gap-1">
                        <AlertCircle size={14} className="text-amber-500" />
                        Signalé
                      </span>
                    ) : (
                      <span className="text-xs text-slate-500 flex items-center gap-1">
                        <Check size={14} className="text-slate-600" />
                        OK
                      </span>
                    )}
                  </td>

                  <td className="p-4 text-right">
                    <ChevronRight
                      size={16}
                      className="text-slate-600 opacity-0 group-hover:opacity-100 transition-opacity"
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {/* Empty state : quand aucun élément ne matche le filtre */}
        {!loading && filtered.length === 0 && (
          <div className="p-12 text-center text-slate-500">Aucune transaction ne correspond à ce filtre.</div>
        )}
      </div>

      {/* Slide-over : détail transaction + actions */}
      <div
        className={`fixed inset-y-0 right-0 w-[480px] bg-[#0f172a] border-l border-slate-800 shadow-2xl transform transition-transform duration-300 z-50 flex flex-col ${
          selectedTx ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {selectedTx &&
          (() => {
            const tx = selectedTx.transaction;
            const score = pickScore(selectedTx);
            const level = computeRiskLevel(score);
            const factors = pickFactors(selectedTx);
            const paymentLabel = getPaymentLabel(selectedTx);

            return (
              <>
                <div className="p-6 border-b border-slate-800 flex justify-between items-start bg-slate-900/50">
                  <div>
                    <h2 className="text-lg font-semibold text-white">Détail du paiement</h2>
                    <p className="text-sm text-slate-500">Réf: {tx.id}</p>
                  </div>
                  <button
                    onClick={() => setSelectedTx(null)}
                    className="p-1 hover:bg-slate-800 rounded text-slate-400 hover:text-white transition-colors"
                  >
                    <X size={20} />
                  </button>
                </div>

                <div className="flex-1 overflow-y-auto p-6 space-y-8">
                  {/* Infos commerçant : repère visuel + tags */}
                  <div className="flex items-center gap-4">
                    <div
                      className={`w-16 h-16 rounded-xl flex items-center justify-center text-white text-2xl font-bold shadow-lg ${getCategoryColor(
                        tx.merchant_category
                      )}`}
                    >
                      {(tx.merchant_name || "?").charAt(0)}
                    </div>
                    <div>
                      <h3 className="text-xl font-bold text-white">{tx.merchant_name}</h3>
                      <div className="flex items-center gap-2 text-sm text-slate-400 mt-1">
                        <span className="px-2 py-0.5 bg-slate-800 rounded text-xs">{tx.merchant_category}</span>
                        <span>•</span>
                        <span>{tx.arrondissement}</span>
                        <span>•</span>
                        <span className="inline-flex items-center gap-1">
                          {getPaymentIcon(paymentLabel)} {paymentLabel}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Résumé : score + guidance produit */}
                  <div className="bg-slate-900 rounded-xl p-5 border border-slate-800">
                    <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-4">Analyse Rapide</h3>
                    <div className="flex items-center gap-4 mb-4">
                      <div
                        className={`w-16 h-16 rounded-full flex items-center justify-center border-4 ${
                          level === RiskLevel.HIGH
                            ? "border-red-500/20 text-red-500 bg-red-500/10"
                            : level === RiskLevel.MEDIUM
                            ? "border-amber-500/20 text-amber-500 bg-amber-500/10"
                            : "border-emerald-500/20 text-emerald-500 bg-emerald-500/10"
                        }`}
                      >
                        <span className="text-xl font-bold">{score}</span>
                      </div>
                      <div>
                        <div className="text-lg font-medium text-white mb-1">Niveau : {getRiskLabel(level)}</div>
                        <div className="text-sm text-slate-400">
                          {level === RiskLevel.HIGH
                            ? "Action immédiate recommandée."
                            : level === RiskLevel.MEDIUM
                            ? "Une vérification simple est conseillée."
                            : "Aucune action requise."}
                        </div>
                        <div className="text-xs text-slate-500 mt-2">
                          Montant :{" "}
                          <span className="font-mono text-slate-200">{safeNumber(tx.amount, 0).toFixed(2)} €</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Facteurs : explication humaine (si dispo) */}
                  <div>
                    <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3">
                      Pourquoi c&apos;est signalé ?
                    </h3>
                    <div className="space-y-3">
                      {factors.map((factor, i) => (
                        <div key={i} className="flex gap-3 p-3 rounded-lg bg-slate-800/50 border border-slate-700/50">
                          <div className="mt-1">
                            <AlertCircle size={16} className="text-blue-400" />
                          </div>
                          <p className="text-sm text-slate-300">{factor}</p>
                        </div>
                      ))}

                      {/* Fallback : score élevé mais pas de facteurs détaillés */}
                      {factors.length === 0 && (
                        <div className="flex gap-3 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                          <Check size={16} className="text-emerald-500 mt-1" />
                          <p className="text-sm text-emerald-300">Score élevé détecté (facteurs non détaillés).</p>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Assistant : explication pédagogique (opt-in) */}
                  <div className="bg-gradient-to-br from-blue-900/10 to-slate-900 rounded-xl p-5 border border-blue-500/20">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2 text-blue-400 font-medium text-sm">
                        <Bot size={18} />
                        <span>Assistant Fraude</span>
                      </div>

                      {!aiAnalysis && (
                        <button
                          onClick={handleAnalyze}
                          disabled={analyzing}
                          className="text-xs bg-blue-600 hover:bg-blue-500 text-white px-3 py-1.5 rounded-lg transition-colors"
                        >
                          {analyzing ? "Analyse..." : "Obtenir une explication"}
                        </button>
                      )}
                    </div>

                    {aiAnalysis && (
                      <div className="text-sm text-slate-300 leading-relaxed bg-slate-900/50 p-3 rounded border border-slate-700/50">
                        {aiAnalysis}
                      </div>
                    )}

                    {!aiAnalysis && !analyzing && (
                      <p className="text-xs text-slate-500">
                        Cliquez pour obtenir une analyse pédagogique de ce dossier.
                      </p>
                    )}
                  </div>

                  {/* Actions dossier : uniquement si une alerte existe */}
                  {selectedTx.alert && (
                    <div className="pt-4 border-t border-slate-800">
                      <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3">Actions possibles</h3>
                      <div className="grid grid-cols-2 gap-3">
                        <button
                          onClick={() => patchAlertStatus("EN_ENQUETE", "Mise en enquête depuis l’onglet Transactions")}
                          className="py-2.5 px-4 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-sm font-medium border border-slate-700 transition-colors"
                        >
                          Mettre en enquête
                        </button>

                        <button
                          onClick={() =>
                            patchAlertStatus("CLOTURE", "Faux positif confirmé depuis l’onglet Transactions")
                          }
                          className="py-2.5 px-4 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-medium transition-colors"
                        >
                          Valider (Faux positif)
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </>
            );
          })()}
      </div>
    </div>
  );
};

export default Transactions;
