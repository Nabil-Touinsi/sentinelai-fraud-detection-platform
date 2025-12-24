// frontend/pages/Dashboard.tsx
import React, { useEffect, useState } from "react";
import { getCategoryColor } from "../types";
import ParisMap from "../components/ParisMap";
import { AreaChart, Area, ResponsiveContainer, Tooltip } from "recharts";
import { CheckCircle2, Clock, AlertTriangle, Activity, MapPin } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { apiFetch } from "../services/api";

/** ✅ Local type (car pas exporté de types.ts chez toi) */
type DashboardStats = {
  totalTransactionsToday: number;
  openAlerts: number;
  criticalAlerts: number;
  avgResolutionTimeMinutes: number;
};

type DashboardSummary = {
  kpis: {
    transactions_total: number;
    transactions_window: number;
    alerts_total: number;
    alerts_open: number;
    alerts_critical: number;
    avg_risk_score_window?: number | null;
  };
  series: {
    days: Array<{
      date: string; // YYYY-MM-DD
      transactions: number;
      alerts: number;
      avg_score?: number | null;
    }>;
  };
  hotspots: {
    arrondissements: Array<{ key: string; count: number; avg_score?: number | null }>;
    categories: Array<{ key: string; count: number; avg_score?: number | null }>;
    merchants: Array<{ key: string; count: number; avg_score?: number | null }>;
  };
};

// Type souple pour /system/status
type SystemStatus = {
  status?: string; // "ok" / "degraded" / ...
  ok?: boolean;

  timestamp?: string;
  ts?: string;

  db?: any;
  database?: any;

  ws?: any;
  websocket?: any;

  alert_threshold?: number;
  threshold?: number;

  model_version?: string;
  version?: string;

  [k: string]: any;
};

function computeSystemOk(s: SystemStatus | null): boolean {
  if (!s) return false;

  if (typeof s.ok === "boolean") return s.ok;
  if (typeof s.status === "string") {
    const v = s.status.toLowerCase();
    if (v === "ok" || v === "healthy" || v === "up") return true;
    if (v === "degraded" || v === "down" || v === "error") return false;
  }

  const db = s.db ?? s.database;
  const ws = s.ws ?? s.websocket;

  const dbOk =
    db == null
      ? true
      : typeof db === "string"
      ? db.toLowerCase() === "ok"
      : typeof db?.ok === "boolean"
      ? db.ok
      : typeof db?.status === "string"
      ? db.status.toLowerCase() === "ok"
      : true;

  const wsOk =
    ws == null
      ? true
      : typeof ws === "string"
      ? ws.toLowerCase() === "ok"
      : typeof ws?.ok === "boolean"
      ? ws.ok
      : typeof ws?.status === "string"
      ? ws.status.toLowerCase() === "ok"
      : true;

  return Boolean(dbOk && wsOk);
}

function formatTs(s: SystemStatus | null): string | null {
  const raw = s?.timestamp || s?.ts;
  if (!raw) return null;
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleTimeString();
}

/** ✅ Compat: backend = score_snapshot, mock = risk_score_snapshot */
function getSnapshot(a: any): number {
  const v = a?.score_snapshot ?? a?.risk_score_snapshot ?? a?.riskScoreSnapshot ?? a?.risk?.score;
  const n = typeof v === "string" ? Number(v) : v;
  return Number.isFinite(n) ? n : 0;
}

/** ✅ Compat: backend = CLOTURE / EN_ENQUETE / A_TRAITER, mock = CLOSED / NEW / ... */
function isClosedStatus(status: any): boolean {
  const s = String(status ?? "").toUpperCase().trim();
  return s === "CLOTURE" || s === "CLOSED";
}

function toZoneParis(arr: any): number | null {
  const s = String(arr ?? "").trim();
  // attendu: "75008", "75010", etc.
  if (s.length === 5 && s.startsWith("75")) {
    const z = parseInt(s.slice(-2), 10);
    if (Number.isFinite(z) && z >= 1 && z <= 20) return z;
  }
  // fallback: "8" ou "Paris 8"
  const m = s.match(/(\d{1,2})$/);
  if (m) {
    const z = parseInt(m[1], 10);
    if (Number.isFinite(z) && z >= 1 && z <= 20) return z;
  }
  return null;
}

function computeAvgResolutionMinutes(alertItems: any[]): number {
  const closed = alertItems.filter((x) => isClosedStatus(x?.status));
  if (closed.length === 0) return 0;

  let sum = 0;
  let n = 0;

  for (const a of closed) {
    const c = new Date(a?.created_at ?? "");
    const u = new Date(a?.updated_at ?? "");
    if (!Number.isNaN(c.getTime()) && !Number.isNaN(u.getTime()) && u.getTime() >= c.getTime()) {
      sum += (u.getTime() - c.getTime()) / 60000;
      n += 1;
    }
  }
  return n ? Math.round(sum / n) : 0;
}

// ✅ Base dérivée de VITE_API_URL (une seule env)
const API_URL =
  (import.meta as any).env?.VITE_API_URL?.toString()?.replace(/\/+$/, "") || "http://127.0.0.1:8000";

const wsBase = API_URL.startsWith("https://")
  ? API_URL.replace("https://", "wss://")
  : API_URL.replace("http://", "ws://");

const Dashboard = () => {
  const navigate = useNavigate();

  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [urgentAlerts, setUrgentAlerts] = useState<any[]>([]);
  const [chartData, setChartData] = useState<any[]>([]);
  const [mapTx, setMapTx] = useState<any[]>([]);

  const [sys, setSys] = useState<SystemStatus | null>(null);
  const [sysOk, setSysOk] = useState<boolean>(false);
  const [sysError, setSysError] = useState<string | null>(null);

  const refreshData = async () => {
  try {
    // 1) Summary (KPI + séries + hotspots)
    const summary = await apiFetch<DashboardSummary>("/dashboard/summary?days=30&top_n=8");

    // 2) Alerts list (pour la todolist + avg resolution)
    const alertsResp = await apiFetch<any>("/alerts?page=1&page_size=200");
    const items = Array.isArray(alertsResp) ? alertsResp : alertsResp?.data ?? [];

    // Normalise en objets "flat" (alert + transaction + risk)
    const flatAlerts = items.map((it: any) => {
      const alert = it?.alert ?? it;
      const tx = it?.transaction ?? it?.tx ?? {};
      const rs = it?.risk_score ?? null;

      return {
        ...alert,
        transaction: tx,
        risk: {
          score: rs?.score ?? alert?.score_snapshot ?? 0,
          factors: alert?.reason ? [alert.reason] : [],
        },
      };
    });

    // --- STATS (branché backend)
    const days = summary?.series?.days ?? [];
    const todayPoint = days.length ? days[days.length - 1] : null;

    const s: DashboardStats = {
      totalTransactionsToday: todayPoint?.transactions ?? 0,
      openAlerts: summary?.kpis?.alerts_open ?? 0,
      criticalAlerts: summary?.kpis?.alerts_critical ?? 0,
      avgResolutionTimeMinutes: computeAvgResolutionMinutes(flatAlerts),
    };
    setStats(s);

    // --- Urgent alerts (top 5 non clôturées)
    setUrgentAlerts(
      flatAlerts
        .filter((a: any) => !isClosedStatus(a?.status))
        .sort((x: any, y: any) => getSnapshot(y) - getSnapshot(x))
        .slice(0, 5)
    );

    // --- Graph: 12 derniers jours d'alertes (plus de random)
    const last12 = days.slice(-12);
    setChartData(
      last12.map((p) => ({
        time: String(p.date ?? "").slice(5), // "MM-DD"
        count: Number(p.alerts ?? 0),
      }))
    );

    // --- Carte Paris: basée sur les hotspots (top arrondissements)
    // IMPORTANT: on fournit aussi "count" pour que ParisMap affiche le vrai volume
    const hotspotTx = (summary?.hotspots?.arrondissements ?? [])
      .map((h) => {
        const zone = toZoneParis(h.key);
        if (!zone) return null;

        const score =
          typeof h.avg_score === "number"
            ? h.avg_score
            : Math.min(100, 30 + Math.round((h.count ?? 0) * 8));

        return {
          id: `hotspot-${zone}`,
          amount: 0,
          zone_paris: zone,
          count: h.count ?? 1,
          risk: { score },
        };
      })
      .filter(Boolean);

    setMapTx(hotspotTx);
  } catch (e) {
    console.error("Dashboard refreshData error:", e);
    // On ne casse pas l'écran si un appel échoue
  }
};

  const refreshSystemStatus = async () => {
    try {
      setSysError(null);
      const s = await apiFetch<SystemStatus>("/system/status");
      setSys(s);
      setSysOk(computeSystemOk(s));
    } catch (e: any) {
      console.error(e);
      setSys(null);
      setSysOk(false);
      setSysError(e?.error?.message ?? e?.message ?? "Erreur /system/status");
    }
  };

  useEffect(() => {
    refreshData();
    refreshSystemStatus();

    const intervalData = setInterval(refreshData, 10000);
const intervalSys = setInterval(refreshSystemStatus, 10000);

    return () => {
      clearInterval(intervalData);
      clearInterval(intervalSys);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!stats) return <div className="p-10 text-slate-500 text-sm">Chargement du tableau de bord...</div>;

  const sysTime = formatTs(sys);
  const threshold = (sys?.alert_threshold ?? sys?.threshold) as number | undefined;

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      {/* Header Status */}
      <div className="flex items-center justify-between bg-slate-900/50 p-4 rounded-xl border border-slate-800">
        <div>
          <h1 className="text-xl font-semibold text-white">Bonjour, Jean</h1>
          <p className="text-slate-400 text-sm">Voici l'état actuel de la surveillance des transactions.</p>

          <div className="text-[11px] text-slate-500 mt-1">
            API: <span className="text-slate-300">{API_URL}</span>
            {typeof threshold === "number" && (
              <>
                {" "}
                • Seuil alerte: <span className="text-slate-300">{threshold}</span>
              </>
            )}
          </div>

          {sysError && (
            <div className="text-[11px] text-red-300 mt-1">
              /system/status indisponible: <span className="text-red-200">{sysError}</span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-3">
          <div className="text-right">
            <div className="text-xs text-slate-500">Dernière mise à jour</div>
            <div className="text-sm font-mono text-slate-300">{sysTime ?? new Date().toLocaleTimeString()}</div>
          </div>

          <div className="h-8 w-[1px] bg-slate-700"></div>

          <div
            className={`flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-full border ${
              sysOk
                ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                : "bg-red-500/10 text-red-300 border-red-500/20"
            }`}
            title={sys ? JSON.stringify(sys, null, 2) : "Aucun statut"}
          >
            <span className="relative flex h-2 w-2">
              <span
                className={`animate-ping absolute inline-flex h-full w-full rounded-full ${
                  sysOk ? "bg-emerald-400" : "bg-red-400"
                } opacity-75`}
              ></span>
              <span
                className={`relative inline-flex rounded-full h-2 w-2 ${sysOk ? "bg-emerald-500" : "bg-red-500"}`}
              ></span>
            </span>
            {sysOk ? "Système Opérationnel" : "Système Dégradé"}
          </div>
        </div>
      </div>

      {/* 4 KPIs Métier */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <KpiCard
          label="Transactions du jour"
          value={stats.totalTransactionsToday}
          icon={<Activity size={18} className="text-blue-400" />}
        />
        <KpiCard
          label="Alertes à traiter"
          value={stats.openAlerts}
          icon={<AlertTriangle size={18} className="text-amber-400" />}
          highlight={stats.openAlerts > 0}
        />
        <KpiCard
          label="Cas critiques"
          value={stats.criticalAlerts}
          icon={<AlertTriangle size={18} className="text-red-400" />}
          isUrgent={stats.criticalAlerts > 0}
        />
        <KpiCard
          label="Temps moy. traitement"
          value={`${stats.avgResolutionTimeMinutes} min`}
          icon={<Clock size={18} className="text-slate-400" />}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* To Do List */}
        <div className="lg:col-span-2 flex flex-col gap-4">
          <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-blue-500"></span>
            À faire maintenant
          </h2>

          <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
            {urgentAlerts.length === 0 ? (
              <div className="p-12 text-center">
                <div className="w-12 h-12 bg-emerald-500/10 rounded-full flex items-center justify-center mx-auto mb-3">
                  <CheckCircle2 size={24} className="text-emerald-500" />
                </div>
                <h3 className="text-white font-medium">Tout est en ordre</h3>
                <p className="text-slate-500 text-sm mt-1">
                  Aucune alerte urgente ne nécessite votre attention immédiate.
                </p>
                <button
                  onClick={() => navigate("/transactions")}
                  className="mt-4 text-sm text-blue-400 hover:text-blue-300 font-medium"
                >
                  Vérifier les dernières transactions &rarr;
                </button>
              </div>
            ) : (
              <div className="divide-y divide-slate-800">
                {urgentAlerts.map((alert: any) => {
                  const tx = alert?.transaction ?? alert?.tx ?? {};
                  const snapshot = getSnapshot(alert);
                  const zone = tx?.zone_paris ?? tx?.arrondissement ?? "";

                  return (
                    <div
                      key={alert?.id ?? Math.random()}
                      className="p-4 flex items-center justify-between hover:bg-slate-800/30 transition-colors group"
                    >
                      <div className="flex items-center gap-4">
                        <div
                          className={`w-12 h-12 rounded-full flex items-center justify-center text-white font-bold text-lg shadow-inner ${getCategoryColor(
                            String(tx?.merchant_category ?? "")
                          )}`}
                        >
                          {String(tx?.merchant_name ?? "T").charAt(0)}
                        </div>

                        <div>
                          <div className="flex items-center gap-2 mb-1">
                            <span
                              className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
                                snapshot > 80
                                  ? "bg-red-500/10 text-red-400 border-red-500/20"
                                  : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                              }`}
                            >
                              {snapshot > 80 ? "URGENT" : "À VÉRIFIER"}
                            </span>
                            <span className="text-xs text-slate-500">
                              {new Date(alert?.created_at ?? Date.now()).toLocaleTimeString()}
                            </span>

                            {zone ? (
                              <span className="text-xs text-slate-500 flex items-center gap-1">
                                <MapPin size={10} /> {String(zone).startsWith("75") ? zone : `Paris ${zone}`}
                              </span>
                            ) : null}
                          </div>

                          <div className="text-sm font-medium text-slate-200">
                            {tx?.merchant_name} • {tx?.amount} €
                          </div>

                          <div className="text-xs text-slate-500">
                            {alert?.risk?.factors?.[0] ?? alert?.reason ?? "Activité suspecte"}
                          </div>
                        </div>
                      </div>

                      <button
                        onClick={() => navigate("/alerts")}
                        className="px-4 py-2 bg-slate-800 hover:bg-white hover:text-slate-900 text-slate-300 text-sm font-medium rounded-lg transition-all border border-slate-700 hover:border-white shadow-sm"
                      >
                        Ouvrir
                      </button>
                    </div>
                  );
                })}

                <div className="p-3 bg-slate-900/50 text-center border-t border-slate-800">
                  <button onClick={() => navigate("/alerts")} className="text-xs text-slate-500 hover:text-slate-300">
                    Voir toutes les alertes ({stats.openAlerts})
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Graph */}
          <div className="mt-4">
            <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-3">
              Volume des alertes (12 derniers jours)
            </h2>
            <div className="h-32 w-full bg-slate-900/30 border border-slate-800 rounded-xl p-2">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="colorAlerts" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#ef4444" stopOpacity={0.2} />
                      <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#1e293b",
                      border: "none",
                      borderRadius: "8px",
                      fontSize: "12px",
                    }}
                    itemStyle={{ color: "#fff" }}
                    cursor={{ stroke: "#334155" }}
                  />
                  <Area
                    type="monotone"
                    dataKey="count"
                    stroke="#ef4444"
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#colorAlerts)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* Right Column */}
        <div className="flex flex-col gap-6">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 h-full flex flex-col">
            <h3 className="text-sm font-semibold text-slate-300 mb-4 flex items-center justify-between">
              <span>Zones les plus signalées</span>
              <span className="text-[10px] bg-slate-800 px-2 py-1 rounded text-slate-400">Paris IM</span>
            </h3>
            <div className="flex-1 min-h-[250px]">
              <ParisMap data={mapTx as any} />
            </div>
            <div className="mt-4 p-3 bg-blue-900/10 border border-blue-900/20 rounded-lg">
              <p className="text-xs text-blue-300 leading-relaxed">
                <span className="font-bold">Info Quartier :</span> Les zones “hotspots” sont calculées à partir des alertes
                des 30 derniers jours.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const KpiCard = ({ label, value, icon, highlight, isUrgent }: any) => (
  <div
    className={`p-5 rounded-xl border flex flex-col justify-between h-24 ${
      isUrgent ? "bg-red-500/10 border-red-500/20" : "bg-slate-900 border-slate-800"
    }`}
  >
    <div className="flex justify-between items-start">
      <span className={`text-xs font-semibold uppercase tracking-wider ${isUrgent ? "text-red-400" : "text-slate-500"}`}>
        {label}
      </span>
      {icon}
    </div>
    <div
      className={`text-2xl font-bold tracking-tight ${
        isUrgent ? "text-red-400" : highlight ? "text-amber-400" : "text-white"
      }`}
    >
      {value}
    </div>
  </div>
);

export default Dashboard;
