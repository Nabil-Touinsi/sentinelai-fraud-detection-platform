import React, { useState } from 'react';
import { MockBackend } from '../services/mockBackend';
import { FullTransactionData, getCategoryColor } from '../types';
import { ArrowRight, Play, Shield, AlertTriangle, CheckCircle } from 'lucide-react';

const Simulator = () => {
  const [loading, setLoading] = useState(false);
  const [lastTx, setLastTx] = useState<FullTransactionData | null>(null);

  const handleInject = async (type: 'NORMAL' | 'FRAUD') => {
    setLoading(true);
    // Utilise le générateur intelligent du backend
    const result = await MockBackend.generateScenario(type);
    setLastTx(result);
    setLoading(false);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8 py-6">
      <div className="text-center mb-10">
        <h1 className="text-3xl font-bold text-white tracking-tight mb-3">Espace Démonstration</h1>
        <p className="text-slate-400 text-lg max-w-2xl mx-auto">
            Testez la réactivité du système en simulant des transactions.
            Observez comment l'outil distingue une opération standard d'un comportement suspect.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        
        {/* Actions */}
        <div className="space-y-4">
            <h2 className="text-sm font-bold text-slate-500 uppercase tracking-wider mb-4">Créer un scénario</h2>
            
            <button 
                onClick={() => handleInject('NORMAL')}
                disabled={loading}
                className="w-full p-6 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded-xl flex items-center gap-4 transition-all group text-left"
            >
                <div className="w-12 h-12 rounded-full bg-emerald-500/10 flex items-center justify-center text-emerald-500 group-hover:bg-emerald-500 group-hover:text-white transition-colors">
                    <Shield size={24} />
                </div>
                <div>
                    <h3 className="text-white font-semibold text-lg">Exemple normal</h3>
                    <p className="text-slate-500 text-sm">Achat quotidien (Supermarché, Transport...), montant cohérent.</p>
                </div>
            </button>

            <button 
                onClick={() => handleInject('FRAUD')}
                disabled={loading}
                className="w-full p-6 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded-xl flex items-center gap-4 transition-all group text-left"
            >
                <div className="w-12 h-12 rounded-full bg-red-500/10 flex items-center justify-center text-red-500 group-hover:bg-red-500 group-hover:text-white transition-colors">
                    <AlertTriangle size={24} />
                </div>
                <div>
                    <h3 className="text-white font-semibold text-lg">Exemple suspect</h3>
                    <p className="text-slate-500 text-sm">Luxe de nuit, montant aberrant pour l'enseigne, tech...</p>
                </div>
            </button>
        </div>

        {/* Result */}
        <div className="bg-slate-950 border border-slate-800 rounded-xl p-6 relative min-h-[300px] flex flex-col">
            <h2 className="text-sm font-bold text-slate-500 uppercase tracking-wider mb-6">Résultat de l'analyse</h2>
            
            {loading ? (
                <div className="flex-1 flex flex-col items-center justify-center text-slate-500">
                    <div className="animate-spin mb-4">
                        <Play size={32} className="text-blue-500" />
                    </div>
                    <p>Simulation transactionnelle et scoring...</p>
                </div>
            ) : lastTx ? (
                <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
                    <div className="flex items-center justify-between mb-6">
                        <div className="flex items-center gap-3">
                             <div className={`w-10 h-10 rounded-full flex items-center justify-center text-white font-bold ${getCategoryColor(lastTx.merchant_category)}`}>
                                {lastTx.merchant_name.charAt(0)}
                             </div>
                             <div>
                                 <div className="text-white font-medium">{lastTx.merchant_name}</div>
                                 <div className="text-xs text-slate-500">{lastTx.merchant_category} • {lastTx.amount} €</div>
                             </div>
                        </div>
                        <div className={`px-4 py-1.5 rounded-full text-sm font-bold border ${lastTx.risk?.level === 'CRITIQUE' ? 'bg-red-500 text-white border-red-600' : 'bg-emerald-500 text-white border-emerald-600'}`}>
                            {lastTx.risk?.level === 'CRITIQUE' ? 'Action Requise' : 'Validé'}
                        </div>
                    </div>

                    <div className="space-y-6">
                         <div>
                            <div className="flex justify-between text-sm mb-2">
                                <span className="text-slate-400">Niveau de risque calculé</span>
                                <span className="text-white font-bold">{lastTx.risk?.score}/100</span>
                            </div>
                            <div className="h-3 w-full bg-slate-800 rounded-full overflow-hidden">
                                <div 
                                    className={`h-full transition-all duration-1000 ${lastTx.risk?.score && lastTx.risk.score > 50 ? 'bg-red-500' : 'bg-emerald-500'}`} 
                                    style={{ width: `${lastTx.risk?.score}%` }}
                                ></div>
                            </div>
                         </div>

                         <div className="bg-slate-900 rounded-lg p-4 border border-slate-800">
                            <span className="text-xs font-bold text-slate-500 uppercase mb-2 block">Explication du système</span>
                            {lastTx.risk?.factors.length ? (
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
                                    Le comportement est cohérent avec l'historique client.
                                </p>
                            )}
                         </div>
                    </div>
                </div>
            ) : (
                <div className="flex-1 flex flex-col items-center justify-center text-slate-600 border-2 border-dashed border-slate-800 rounded-lg bg-slate-900/30">
                    <p>En attente d'une simulation...</p>
                </div>
            )}
        </div>

      </div>
    </div>
  );
};

export default Simulator;