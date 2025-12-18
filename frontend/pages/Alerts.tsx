// frontend/pages/Alerts.tsx
import React, { useEffect, useMemo, useRef, useState } from "react";
import { Inbox, CheckCircle, Clock, ChevronRight } from "lucide-react";
import {
  AlertStatus,
  AlertListItem,
  AlertsListResponse,
  getCategoryColor,
  normalizeAlertStatus,
} from "../types";

const POLL_MS = 7000;

const apiBase =
  (import.meta as any).env?.VITE_API_BASE_URL?.replace(/\/$/, "") ||
  "http://127.0.0.1:8000";

const wsBase = apiBase.startsWith("https://")
  ? apiBase.replace("https://", "wss://")
  : apiBase.replace("http://", "ws://");

type RtMode = "WebSocket" | "Polling";
type TabKey = AlertStatus;

type TabButtonProps = {
  label: string;
  count: number;
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
};

const TabButton = ({ label, count, active, onClick, icon }: TabButtonProps) => (
  <button
    onClick={onClick}
    className={`flex items-center gap-2 px-6 py-4 text-sm font-medium border-b-2 transition-colors ${
      active
        ? "border-blue-500 text-blue-400"
        : "border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-700"
    }`}
  >
    {icon}
    {label}
    {count > 0 && (
      <span
        className={`text-[10px] px-2 py-0.5 rounded-full ${
          active ? "bg-blue-500/20 text-blue-400" : "bg-slate-800 text-slate-400"
        }`}
      >
        {count}
      </span>
    )}
  </button>
);

const Alerts = () => {
  const [items, setItems] = useState<AlertListItem[]>([]);
  const [activeTab, setActiveTab] = useState<TabKey>(AlertStatus.A_TRAITER);
  const [rtMode, setRtMode] = useState<RtMode>("Polling");

  const wsRef = useRef<WebSocket | null>(null);
  const pollRef = useRef<number | null>(null);
  const destroyedRef = useRef(false);
  const connectingRef = useRef(false);

  const fetchAlerts = async () => {
    const url = `${apiBase}/alerts?page=1&page_size=200&sort_by=priority&order=desc`;
    const res = await fetch(url, { credentials: "include" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const json = (await res.json()) as AlertsListResponse;
    setItems(json.data ?? []);
  };

  const counts = useMemo(() => {
    const c = { a: 0, e: 0, cl: 0 };
    for (const it of items) {
      const st = normalizeAlertStatus(it.alert.status);
      if (st === AlertStatus.A_TRAITER) c.a++;
      else if (st === AlertStatus.EN_ENQUETE) c.e++;
      else if (st === AlertStatus.CLOTURE) c.cl++;
    }
    return c;
  }, [items]);

  const currentList = useMemo(() => {
    return items.filter((it) => normalizeAlertStatus(it.alert.status) === activeTab);
  }, [items, activeTab]);

  const patchAlert = async (alertId: string, status: AlertStatus, comment?: string) => {
    const res = await fetch(`${apiBase}/alerts/${alertId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ status, comment: comment || "" }),
    });

    if (!res.ok) {
      const txt = await res.text();
      throw new Error(txt || `PATCH failed (${res.status})`);
    }
  };

  const moveAlert = async (alertId: string, newStatus: AlertStatus) => {
    // optimistic UI
    setItems((prev) =>
      prev.map((it) =>
        it.alert.id === alertId
          ? {
              ...it,
              alert: { ...it.alert, status: newStatus, updated_at: new Date().toISOString() },
            }
          : it
      )
    );

    try {
      await patchAlert(alertId, newStatus, "Changement de statut via UI");
      await fetchAlerts();
    } catch (e) {
      console.error(e);
      await fetchAlerts(); // rollback by refresh
    }
  };

  // initial load
  useEffect(() => {
    destroyedRef.current = false;
    fetchAlerts().catch(console.error);
    return () => {
      destroyedRef.current = true;
    };
  }, []);

  // WS + fallback polling
  useEffect(() => {
    const startPolling = () => {
      setRtMode("Polling");
      if (!pollRef.current) {
        pollRef.current = window.setInterval(() => {
          fetchAlerts().catch(console.error);
        }, POLL_MS);
      }
    };

    const stopPolling = () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
      pollRef.current = null;
    };

    const connectWs = () => {
      if (destroyedRef.current) return;
      if (connectingRef.current) return;
      connectingRef.current = true;

      try {
        const ws = new WebSocket(`${wsBase}/ws/alerts`);
        wsRef.current = ws;

        ws.onopen = () => {
          connectingRef.current = false;
          setRtMode("WebSocket");
          stopPolling();
        };

        ws.onmessage = (ev) => {
          try {
            const msg = JSON.parse(ev.data);
            if (
              msg?.type === "ALERT_CREATED" ||
              msg?.type === "ALERT_STATUS_CHANGED" ||
              msg?.type === "SCORE_COMPUTED"
            ) {
              fetchAlerts().catch(console.error);
            }
          } catch {
            // ignore
          }
        };

        ws.onerror = () => {
          // onclose will handle fallback
        };

        ws.onclose = () => {
          connectingRef.current = false;
          wsRef.current = null;
          startPolling();
          if (!destroyedRef.current) {
            window.setTimeout(connectWs, 1500);
          }
        };
      } catch {
        connectingRef.current = false;
        startPolling();
      }
    };

    connectWs();

    return () => {
      destroyedRef.current = true;
      if (wsRef.current) wsRef.current.close();
      wsRef.current = null;
      if (pollRef.current) window.clearInterval(pollRef.current);
      pollRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="max-w-4xl mx-auto py-6">
      <div className="mb-8 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Gestion des dossiers</h1>
          <p className="text-slate-400 text-sm">Traitez les signalements prioritaires.</p>
        </div>

        <div className="text-xs px-3 py-2 rounded-lg border border-slate-800 bg-slate-900/50 text-slate-300">
          Temps réel :{" "}
          <span className={rtMode === "WebSocket" ? "text-emerald-400" : "text-amber-400"}>
            {rtMode === "WebSocket" ? "WebSocket" : `Polling (${POLL_MS / 1000}s)`}
          </span>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-800 mb-6">
        <TabButton
          label="À traiter"
          count={counts.a}
          active={activeTab === AlertStatus.A_TRAITER}
          onClick={() => setActiveTab(AlertStatus.A_TRAITER)}
          icon={<Inbox size={16} />}
        />
        <TabButton
          label="En cours d'enquête"
          count={counts.e}
          active={activeTab === AlertStatus.EN_ENQUETE}
          onClick={() => setActiveTab(AlertStatus.EN_ENQUETE)}
          icon={<Clock size={16} />}
        />
        <TabButton
          label="Clôturés / Traités"
          count={counts.cl}
          active={activeTab === AlertStatus.CLOTURE}
          onClick={() => setActiveTab(AlertStatus.CLOTURE)}
          icon={<CheckCircle size={16} />}
        />
      </div>

      {/* List Content */}
      <div className="space-y-3">
        {currentList.length === 0 ? (
          <div className="py-20 text-center bg-slate-900/50 rounded-xl border border-slate-800 border-dashed">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-slate-800 mb-4 text-slate-500">
              <CheckCircle size={24} />
            </div>
            <h3 className="text-slate-300 font-medium">Aucun dossier dans cette liste</h3>
            <p className="text-slate-500 text-sm mt-1">Tout est à jour pour le moment.</p>
          </div>
        ) : (
          currentList.map((it) => {
            const alert = it.alert;
            const tx = it.transaction;

            const score = Number(alert.score_snapshot ?? 0);
            const scoreClass =
              score >= 80
                ? "bg-red-500/10 border-red-500/20 text-red-500"
                : "bg-amber-500/10 border-amber-500/20 text-amber-500";

            const amount = typeof tx.amount === "string" ? Number(tx.amount) : tx.amount;

            return (
              <div
                key={alert.id}
                className="bg-slate-900 hover:bg-slate-800/80 border border-slate-800 rounded-lg p-5 transition-all shadow-sm flex items-center justify-between group"
              >
                <div className="flex items-center gap-5">
                  <div
                    className={`flex flex-col items-center justify-center w-12 h-12 rounded-lg border ${scoreClass}`}
                  >
                    <span className="text-lg font-bold">{score}</span>
                  </div>

                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-bold text-white ${getCategoryColor(
                          tx.merchant_category
                        )}`}
                      >
                        {tx.merchant_category}
                      </span>
                      <span className="text-slate-600 text-[10px]">•</span>
                      <span className="text-xs text-slate-400">
                        {new Date(alert.created_at).toLocaleString()}
                      </span>
                    </div>

                    <div className="text-white font-medium flex items-center gap-2">
                      {tx.merchant_name}
                      <span className="text-slate-500 font-normal">|</span>
                      <span className="text-slate-200 font-mono">
                        {Number.isFinite(amount) ? amount.toFixed(2) : tx.amount} {tx.currency}
                      </span>
                    </div>

                    <div className="text-sm text-slate-400 mt-0.5">
                      Raison: {alert.reason || "Score élevé détecté"}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  {activeTab === AlertStatus.A_TRAITER && (
                    <button
                      onClick={() => moveAlert(alert.id, AlertStatus.EN_ENQUETE)}
                      className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors"
                    >
                      Ouvrir l'enquête
                    </button>
                  )}

                  {activeTab === AlertStatus.EN_ENQUETE && (
                    <button
                      onClick={() => moveAlert(alert.id, AlertStatus.CLOTURE)}
                      className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded-lg transition-colors"
                    >
                      Clôturer (OK)
                    </button>
                  )}

                  <button className="p-2 text-slate-500 hover:text-white hover:bg-slate-700 rounded-lg transition-colors">
                    <ChevronRight size={20} />
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

export default Alerts;
