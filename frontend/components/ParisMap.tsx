import React from 'react';
import { FullTransactionData } from '../types';

interface Props {
  data: FullTransactionData[];
}

const ParisMap: React.FC<Props> = ({ data }) => {
  // Calcul densité risque
  const zoneStats = Array(20).fill(0).map((_, i) => {
    const zoneId = i + 1;
    const txInZone = data.filter(t => t.zone_paris === zoneId);
    if (txInZone.length === 0) return { count: 0, avgRisk: 0 };
    
    const avgRisk = txInZone.reduce((acc, curr) => acc + (curr.risk?.score || 0), 0) / txInZone.length;
    return { count: txInZone.length, avgRisk };
  });

  const getColor = (risk: number, count: number) => {
    if (count === 0) return 'bg-slate-800/50 border-slate-800 text-slate-600';
    if (risk < 40) return 'bg-emerald-500/20 border-emerald-500/30 text-emerald-400';
    if (risk < 70) return 'bg-amber-500/20 border-amber-500/30 text-amber-400';
    return 'bg-red-500/20 border-red-500/30 text-red-400 shadow-[0_0_15px_rgba(239,68,68,0.2)] animate-pulse';
  };

  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 grid grid-cols-5 gap-2">
        {zoneStats.map((stat, idx) => (
          <div 
            key={idx}
            className={`
              relative rounded flex flex-col items-center justify-center border text-[10px] font-mono cursor-help group transition-all duration-300
              ${getColor(stat.avgRisk, stat.count)}
            `}
          >
            <span className="font-bold">{idx + 1}</span>
            
            {/* Tooltip */}
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-40 bg-slate-800 border border-slate-600 p-3 rounded shadow-xl hidden group-hover:block z-20 text-center pointer-events-none">
                <div className="text-white font-bold mb-1">Paris {idx+1}</div>
                <div className="text-slate-300 text-[10px]">Signalements: {stat.count}</div>
                {stat.count > 0 && <div className="text-slate-400 text-[10px]">Risque Moy: {Math.round(stat.avgRisk)}/100</div>}
            </div>
          </div>
        ))}
      </div>
      <div className="mt-3 flex justify-between text-[10px] text-slate-500 font-medium">
        <span>Activité normale</span>
        <span>Signalements fréquents</span>
      </div>
      <div className="h-1 w-full bg-gradient-to-r from-emerald-900/50 via-amber-900/50 to-red-900 rounded-full mt-1"></div>
    </div>
  );
};

export default ParisMap;