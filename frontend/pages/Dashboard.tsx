import React, { useEffect, useState } from 'react';
import { MockBackend } from '../services/mockBackend';
import { DashboardStats, getCategoryColor } from '../types';
import ParisMap from '../components/ParisMap';
import { AreaChart, Area, ResponsiveContainer, Tooltip } from 'recharts';
import { CheckCircle2, Clock, AlertTriangle, Activity, MapPin } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const Dashboard = () => {
  const navigate = useNavigate();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [urgentAlerts, setUrgentAlerts] = useState<any[]>([]);
  const [chartData, setChartData] = useState<any[]>([]);

  const refreshData = async () => {
    const s = await MockBackend.getStats();
    const a = await MockBackend.getAlerts();
    
    setStats(s);
    // Top 5 alertes critiques 'NEW' ou 'IN_REVIEW'
    setUrgentAlerts(a.filter(alert => alert.status !== 'CLOTURE').sort((a, b) => b.risk_score_snapshot - a.risk_score_snapshot).slice(0, 5));
    
    // Génération dummy data simple pour le graph
    const now = new Date().getHours();
    const data = Array.from({ length: 12 }, (_, i) => ({
        time: `${Math.max(0, now - 11 + i)}h`,
        count: Math.floor(Math.random() * 8) + 1 // Nombre d'alertes
    }));
    setChartData(data);
  };

  useEffect(() => {
    refreshData();
    const interval = setInterval(refreshData, 3000); 
    return () => clearInterval(interval);
  }, []);

  if (!stats) return <div className="p-10 text-slate-500 text-sm">Chargement du tableau de bord...</div>;

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      
      {/* Header Status */}
      <div className="flex items-center justify-between bg-slate-900/50 p-4 rounded-xl border border-slate-800">
        <div>
            <h1 className="text-xl font-semibold text-white">Bonjour, Jean</h1>
            <p className="text-slate-400 text-sm">Voici l'état actuel de la surveillance des transactions.</p>
        </div>
        <div className="flex items-center gap-3">
             <div className="text-right">
                <div className="text-xs text-slate-500">Dernière mise à jour</div>
                <div className="text-sm font-mono text-slate-300">{new Date().toLocaleTimeString()}</div>
             </div>
             <div className="h-8 w-[1px] bg-slate-700"></div>
             <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-500/10 text-emerald-400 text-xs font-medium rounded-full border border-emerald-500/20">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
                Système Opérationnel
            </div>
        </div>
      </div>

      {/* 4 KPIs Métier */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <KpiCard 
            label="Transactions du jour" 
            value={stats.totalTransactionsToday} 
            icon={<Activity size={18} className="text-blue-400"/>} 
        />
        <KpiCard 
            label="Alertes à traiter" 
            value={stats.openAlerts} 
            icon={<AlertTriangle size={18} className="text-amber-400"/>} 
            highlight={stats.openAlerts > 0}
        />
        <KpiCard 
            label="Cas critiques" 
            value={stats.criticalAlerts} 
            icon={<AlertTriangle size={18} className="text-red-400"/>}
            isUrgent={stats.criticalAlerts > 0}
        />
        <KpiCard 
            label="Temps moy. traitement" 
            value={`${stats.avgResolutionTimeMinutes} min`} 
            icon={<Clock size={18} className="text-slate-400"/>} 
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* To Do List (Main Focus) */}
        <div className="lg:col-span-2 flex flex-col gap-4">
            <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                À faire maintenant
            </h2>
            
            <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
                {urgentAlerts.length === 0 ? (
                    <div className="p-12 text-center">
                        <div className="w-12 h-12 bg-emerald-500/10 rounded-full flex items-center justify-center mx-auto mb-3">
                            <CheckCircle2 size={24} className="text-emerald-500"/>
                        </div>
                        <h3 className="text-white font-medium">Tout est en ordre</h3>
                        <p className="text-slate-500 text-sm mt-1">Aucune alerte urgente ne nécessite votre attention immédiate.</p>
                        <button onClick={() => navigate('/transactions')} className="mt-4 text-sm text-blue-400 hover:text-blue-300 font-medium">
                            Vérifier les dernières transactions &rarr;
                        </button>
                    </div>
                ) : (
                    <div className="divide-y divide-slate-800">
                        {urgentAlerts.map(alert => (
                            <div key={alert.id} className="p-4 flex items-center justify-between hover:bg-slate-800/30 transition-colors group">
                                <div className="flex items-center gap-4">
                                    {/* Merchant Logo Mock */}
                                    <div className={`w-12 h-12 rounded-full flex items-center justify-center text-white font-bold text-lg shadow-inner ${getCategoryColor(alert.transaction.merchant_category)}`}>
                                        {alert.transaction.merchant_name.charAt(0)}
                                    </div>
                                    
                                    <div>
                                        <div className="flex items-center gap-2 mb-1">
                                            <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${alert.risk_score_snapshot > 80 ? 'bg-red-500/10 text-red-400 border-red-500/20' : 'bg-amber-500/10 text-amber-400 border-amber-500/20'}`}>
                                                {alert.risk_score_snapshot > 80 ? 'URGENT' : 'À VÉRIFIER'}
                                            </span>
                                            <span className="text-xs text-slate-500">{new Date(alert.created_at).toLocaleTimeString()}</span>
                                            <span className="text-xs text-slate-500 flex items-center gap-1">
                                                <MapPin size={10} /> Paris {alert.transaction.zone_paris}
                                            </span>
                                        </div>
                                        <div className="text-sm font-medium text-slate-200">
                                            {alert.transaction.merchant_name} • {alert.transaction.amount} €
                                        </div>
                                        <div className="text-xs text-slate-500">
                                            {alert.risk.factors[0] || 'Activité suspecte'}
                                        </div>
                                    </div>
                                </div>
                                <button 
                                    onClick={() => navigate('/alerts')} 
                                    className="px-4 py-2 bg-slate-800 hover:bg-white hover:text-slate-900 text-slate-300 text-sm font-medium rounded-lg transition-all border border-slate-700 hover:border-white shadow-sm"
                                >
                                    Ouvrir
                                </button>
                            </div>
                        ))}
                         <div className="p-3 bg-slate-900/50 text-center border-t border-slate-800">
                            <button onClick={() => navigate('/alerts')} className="text-xs text-slate-500 hover:text-slate-300">
                                Voir toutes les alertes ({stats.openAlerts})
                            </button>
                        </div>
                    </div>
                )}
            </div>

            {/* Simple Trend Graph */}
             <div className="mt-4">
                <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-3">Volume des alertes (12h)</h2>
                <div className="h-32 w-full bg-slate-900/30 border border-slate-800 rounded-xl p-2">
                    <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={chartData}>
                            <defs>
                                <linearGradient id="colorAlerts" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#ef4444" stopOpacity={0.2}/>
                                <stop offset="95%" stopColor="#ef4444" stopOpacity={0}/>
                                </linearGradient>
                            </defs>
                            <Tooltip 
                                contentStyle={{ backgroundColor: '#1e293b', border: 'none', borderRadius: '8px', fontSize: '12px' }}
                                itemStyle={{ color: '#fff' }}
                                cursor={{ stroke: '#334155' }}
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

        {/* Right Column: Context */}
        <div className="flex flex-col gap-6">
             <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 h-full flex flex-col">
                <h3 className="text-sm font-semibold text-slate-300 mb-4 flex items-center justify-between">
                    <span>Zones les plus signalées</span>
                    <span className="text-[10px] bg-slate-800 px-2 py-1 rounded text-slate-400">Paris IM</span>
                </h3>
                <div className="flex-1 min-h-[250px]">
                    <ParisMap data={[]} />
                </div>
                <div className="mt-4 p-3 bg-blue-900/10 border border-blue-900/20 rounded-lg">
                    <p className="text-xs text-blue-300 leading-relaxed">
                        <span className="font-bold">Info Quartier :</span> Une légère hausse des signalements est observée dans le 8ème arrondissement (Secteur Luxe).
                    </p>
                </div>
             </div>
        </div>

      </div>
    </div>
  );
};

const KpiCard = ({ label, value, icon, highlight, isUrgent }: any) => (
  <div className={`p-5 rounded-xl border flex flex-col justify-between h-24 ${isUrgent ? 'bg-red-500/10 border-red-500/20' : 'bg-slate-900 border-slate-800'}`}>
    <div className="flex justify-between items-start">
        <span className={`text-xs font-semibold uppercase tracking-wider ${isUrgent ? 'text-red-400' : 'text-slate-500'}`}>{label}</span>
        {icon}
    </div>
    <div className={`text-2xl font-bold tracking-tight ${isUrgent ? 'text-red-400' : highlight ? 'text-amber-400' : 'text-white'}`}>
        {value}
    </div>
  </div>
);

export default Dashboard;