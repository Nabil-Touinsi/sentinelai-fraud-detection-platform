import React, { useEffect, useState } from 'react';
import { MockBackend } from '../services/mockBackend';
import { FullTransactionData, RiskLevel, getRiskLabel, getRiskColor, getCategoryColor } from '../types';
import { explainRiskWithGemini } from '../services/gemini';
import { X, ChevronRight, Bot, Check, AlertCircle, CreditCard, Smartphone, Globe } from 'lucide-react';

const Transactions = () => {
  const [transactions, setTransactions] = useState<FullTransactionData[]>([]);
  const [selectedTx, setSelectedTx] = useState<FullTransactionData | null>(null);
  const [filter, setFilter] = useState<'ALL' | 'HIGH' | 'CHECK'>('ALL');
  
  // AI State
  const [aiAnalysis, setAiAnalysis] = useState('');
  const [analyzing, setAnalyzing] = useState(false);

  useEffect(() => {
    MockBackend.getTransactions().then(setTransactions);
  }, []);

  // Filter Logic
  const filtered = transactions.filter(t => {
      if (filter === 'HIGH') return t.risk?.level === RiskLevel.HIGH;
      if (filter === 'CHECK') return t.risk?.level === RiskLevel.MEDIUM;
      return true;
  });

  const handleRowClick = (tx: FullTransactionData) => {
    setSelectedTx(tx);
    setAiAnalysis('');
  };

  const handleAnalyze = async () => {
    if(!selectedTx) return;
    setAnalyzing(true);
    const text = await explainRiskWithGemini(selectedTx);
    setAiAnalysis(text);
    setAnalyzing(false);
  };

  const getPaymentIcon = (method: string) => {
    if (method === 'En ligne') return <Globe size={12}/>;
    if (['Apple Pay', 'Sans Contact', 'Google Pay'].includes(method)) return <Smartphone size={12}/>;
    return <CreditCard size={12}/>;
  };

  return (
    <div className="relative h-[calc(100vh-100px)] flex flex-col">
      {/* Header & Quick Filters */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white tracking-tight">Transactions récentes</h1>
        <p className="text-slate-400 text-sm mb-4">Historique des flux pour analyse et contrôle.</p>
        
        <div className="flex items-center gap-2">
            <button 
                onClick={() => setFilter('ALL')} 
                className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${filter === 'ALL' ? 'bg-slate-700 text-white border-slate-600' : 'bg-transparent text-slate-500 border-slate-800 hover:border-slate-600'}`}
            >
                Tout voir
            </button>
            <button 
                onClick={() => setFilter('HIGH')} 
                className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${filter === 'HIGH' ? 'bg-red-500/10 text-red-400 border-red-500/20' : 'bg-transparent text-slate-500 border-slate-800 hover:border-slate-600'}`}
            >
                Cas Urgents
            </button>
            <button 
                onClick={() => setFilter('CHECK')} 
                className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${filter === 'CHECK' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' : 'bg-transparent text-slate-500 border-slate-800 hover:border-slate-600'}`}
            >
                À vérifier
            </button>
        </div>
      </div>

      {/* Table */}
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
            {filtered.map((tx) => {
              const riskColor = getRiskColor(tx.risk?.level);
              return (
              <tr 
                key={tx.id} 
                onClick={() => handleRowClick(tx)}
                className={`cursor-pointer transition-colors group ${selectedTx?.id === tx.id ? 'bg-blue-900/10' : 'hover:bg-slate-800/50'}`}
              >
                <td className="p-4 font-mono text-xs">{new Date(tx.timestamp).toLocaleTimeString()}</td>
                <td className="p-4">
                    <div className="flex items-center gap-3">
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold ${getCategoryColor(tx.merchant_category)}`}>
                            {tx.merchant_name.charAt(0)}
                        </div>
                        <div>
                            <div className="text-slate-200 font-medium">{tx.merchant_name}</div>
                            <div className="text-xs text-slate-500 flex items-center gap-1.5">
                                {tx.merchant_category} • Paris {tx.zone_paris}
                            </div>
                        </div>
                    </div>
                </td>
                <td className="p-4 text-right">
                    <div className="font-mono text-slate-200 font-medium">{tx.amount.toFixed(2)} €</div>
                    <div className="text-[10px] text-slate-500 flex items-center justify-end gap-1 mt-0.5">
                        {getPaymentIcon(tx.payment_method)} {tx.payment_method}
                    </div>
                </td>
                <td className="p-4">
                   <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${riskColor}`}>
                        {tx.risk?.score}/100 • {getRiskLabel(tx.risk?.level || RiskLevel.LOW)}
                   </span>
                </td>
                <td className="p-4">
                  {tx.alert ? (
                    <span className="text-xs text-slate-400 flex items-center gap-1">
                        <AlertCircle size={14} className="text-amber-500"/>
                        Signalé
                    </span>
                  ) : (
                    <span className="text-xs text-slate-500 flex items-center gap-1">
                        <Check size={14} className="text-slate-600"/>
                        OK
                    </span>
                  )}
                </td>
                <td className="p-4 text-right">
                    <ChevronRight size={16} className="text-slate-600 opacity-0 group-hover:opacity-100 transition-opacity" />
                </td>
              </tr>
            )})}
          </tbody>
        </table>
        {filtered.length === 0 && (
            <div className="p-12 text-center text-slate-500">
                Aucune transaction ne correspond à ce filtre.
            </div>
        )}
      </div>

      {/* Detail Slide-over */}
      <div className={`fixed inset-y-0 right-0 w-[480px] bg-[#0f172a] border-l border-slate-800 shadow-2xl transform transition-transform duration-300 z-50 flex flex-col ${selectedTx ? 'translate-x-0' : 'translate-x-full'}`}>
        {selectedTx && (
            <>
                <div className="p-6 border-b border-slate-800 flex justify-between items-start bg-slate-900/50">
                    <div>
                        <h2 className="text-lg font-semibold text-white">Détail du paiement</h2>
                        <p className="text-sm text-slate-500">Réf: {selectedTx.id}</p>
                    </div>
                    <button onClick={() => setSelectedTx(null)} className="p-1 hover:bg-slate-800 rounded text-slate-400 hover:text-white transition-colors">
                        <X size={20} />
                    </button>
                </div>

                <div className="flex-1 overflow-y-auto p-6 space-y-8">
                    
                    {/* Header Merchant Info */}
                    <div className="flex items-center gap-4">
                        <div className={`w-16 h-16 rounded-xl flex items-center justify-center text-white text-2xl font-bold shadow-lg ${getCategoryColor(selectedTx.merchant_category)}`}>
                            {selectedTx.merchant_name.charAt(0)}
                        </div>
                        <div>
                            <h3 className="text-xl font-bold text-white">{selectedTx.merchant_name}</h3>
                            <div className="flex items-center gap-2 text-sm text-slate-400 mt-1">
                                <span className="px-2 py-0.5 bg-slate-800 rounded text-xs">{selectedTx.merchant_category}</span>
                                <span>•</span>
                                <span>Paris {selectedTx.zone_paris}ème</span>
                            </div>
                        </div>
                    </div>

                    {/* Summary Block */}
                    <div className="bg-slate-900 rounded-xl p-5 border border-slate-800">
                        <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-4">Analyse Rapide</h3>
                        <div className="flex items-center gap-4 mb-4">
                            <div className={`w-16 h-16 rounded-full flex items-center justify-center border-4 ${selectedTx.risk?.level === RiskLevel.HIGH ? 'border-red-500/20 text-red-500 bg-red-500/10' : selectedTx.risk?.level === RiskLevel.MEDIUM ? 'border-amber-500/20 text-amber-500 bg-amber-500/10' : 'border-emerald-500/20 text-emerald-500 bg-emerald-500/10'}`}>
                                <span className="text-xl font-bold">{selectedTx.risk?.score}</span>
                            </div>
                            <div>
                                <div className="text-lg font-medium text-white mb-1">
                                    Niveau : {getRiskLabel(selectedTx.risk?.level || RiskLevel.LOW)}
                                </div>
                                <div className="text-sm text-slate-400">
                                    {selectedTx.risk?.level === RiskLevel.HIGH 
                                        ? "Action immédiate recommandée." 
                                        : selectedTx.risk?.level === RiskLevel.MEDIUM 
                                            ? "Une vérification simple est conseillée." 
                                            : "Aucune action requise."}
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* "Why" Block */}
                    <div>
                        <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3">Pourquoi c'est signalé ?</h3>
                        <div className="space-y-3">
                            {selectedTx.risk?.factors.map((factor, i) => (
                                <div key={i} className="flex gap-3 p-3 rounded-lg bg-slate-800/50 border border-slate-700/50">
                                    <div className="mt-1">
                                        <AlertCircle size={16} className="text-blue-400" />
                                    </div>
                                    <p className="text-sm text-slate-300">{factor}</p>
                                </div>
                            ))}
                             {selectedTx.risk?.factors.length === 0 && (
                                <div className="flex gap-3 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                                    <Check size={16} className="text-emerald-500 mt-1"/>
                                    <p className="text-sm text-emerald-300">Transaction cohérente avec les habitudes.</p>
                                </div>
                            )}
                        </div>
                    </div>

                     {/* AI Assistant */}
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
                                    {analyzing ? 'Analyse...' : 'Obtenir une explication'}
                                </button>
                             )}
                         </div>
                         {aiAnalysis && (
                            <div className="text-sm text-slate-300 leading-relaxed bg-slate-900/50 p-3 rounded border border-slate-700/50 animate-in fade-in">
                                {aiAnalysis}
                            </div>
                         )}
                         {!aiAnalysis && !analyzing && (
                             <p className="text-xs text-slate-500">Cliquez pour obtenir une analyse pédagogique de ce dossier.</p>
                         )}
                     </div>

                     {/* Actions */}
                     {selectedTx.alert && (
                        <div className="pt-4 border-t border-slate-800">
                            <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3">Actions possibles</h3>
                            <div className="grid grid-cols-2 gap-3">
                                <button className="py-2.5 px-4 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-sm font-medium border border-slate-700 transition-colors">
                                    Mettre en enquête
                                </button>
                                <button className="py-2.5 px-4 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-medium transition-colors">
                                    Valider (Faux positif)
                                </button>
                            </div>
                        </div>
                     )}

                </div>
            </>
        )}
      </div>
    </div>
  );
};

export default Transactions;