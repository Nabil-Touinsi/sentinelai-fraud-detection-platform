import React from "react";
import { FullTransactionData } from "../types";

/**
 * Composant ParisMap
 *
 * Rôle :
 * - Affiche une “heatmap” simplifiée de Paris sous forme d’une grille 1..20 (arrondissements).
 * - Chaque case représente un arrondissement et affiche :
 *   - le numéro (1..20)
 *   - un badge avec le nombre de signalements/transactions (count)
 *   - un tooltip (au survol) avec détails (count + risque moyen)
 *
 * Données attendues :
 * - `data: FullTransactionData[]`
 * - Chaque item est supposé contenir :
 *   - `zone_paris: number` (1..20)
 *   - `count?: number` (facultatif, sinon 1)
 *   - `risk?.score?: number` (0..100)
 */

interface Props {
  data: FullTransactionData[];
}

/**
 * quantile(sorted, q)
 * - Calcule un quantile q (ex: 0.33, 0.66) sur un tableau TRIÉ.
 * - Méthode : interpolation linéaire entre deux valeurs adjacentes.
 *
 * Utilisation ici :
 * - Définir des seuils dynamiques (q33 / q66) à partir des zones actives,
 *   pour avoir un rendu vert/orange/rouge même si les volumes changent.
 */
function quantile(sorted: number[], q: number): number {
  if (!sorted.length) return 0;
  const pos = (sorted.length - 1) * q;
  const base = Math.floor(pos);
  const rest = pos - base;
  const next = sorted[base + 1] ?? sorted[base];
  return sorted[base] + rest * (next - sorted[base]);
}

const ParisMap: React.FC<Props> = ({ data }) => {
  /**
   * zoneStats (taille 20)
   * - Pour chaque arrondissement (1..20), on calcule :
   *   - count : somme des counts des items de cette zone (fallback 1)
   *   - avgRisk : moyenne pondérée des scores de risque par count
   *
   * Pourquoi pondérée ?
   * - Si un item représente plusieurs transactions via `count`,
   *   il “pèse” plus dans la moyenne de risque.
   */
  const zoneStats = Array(20)
    .fill(0)
    .map((_, i) => {
      const zoneId = i + 1;

      // Filtre : ne garde que les lignes correspondant à cet arrondissement
      const items = data.filter((t) => t.zone_paris === zoneId);

      // Pas de données => case "inactive"
      if (items.length === 0) return { count: 0, avgRisk: 0 };

      // Total d’occurrences/transactions (en tenant compte de count)
      const totalCount = items.reduce((acc, curr) => acc + (curr.count ?? 1), 0);

      // Somme pondérée des risques : score * count
      const weightedRiskSum = items.reduce((acc, curr) => {
        const c = curr.count ?? 1;

        // score attendu 0..100 (comme ton tooltip l'affiche)
        const r = curr.risk?.score ?? 0;
        return acc + r * c;
      }, 0);

      // Moyenne pondérée
      const avgRisk = totalCount > 0 ? weightedRiskSum / totalCount : 0;

      return { count: totalCount, avgRisk };
    });

  /**
   * Seuils dynamiques q33 / q66
   * - On prend seulement les zones actives (count > 0)
   * - On trie les counts
   * - On calcule 33% et 66% pour découper :
   *   - faible activité => vert
   *   - activité moyenne => orange
   *   - forte activité => rouge
   *
   * Fallback si peu de données :
   * - q33 = 2 et q66 = 5 
   */
  const activeCounts = zoneStats
    .map((z) => z.count)
    .filter((c) => Number.isFinite(c) && c > 0)
    .sort((a, b) => a - b);

  const q33 = activeCounts.length >= 3 ? quantile(activeCounts, 0.33) : 2;
  const q66 = activeCounts.length >= 3 ? quantile(activeCounts, 0.66) : 5;

  /**
   * getColor(risk, count)
   * - Renvoie des classes Tailwind selon :
   *   - count (intensité de trafic / signalements) => vert/orange/rouge
   *   - risk (risque moyen) => ajoute un glow + pulse si risque élevé (>=70)
   *
   * Logique :
   * - count=0 => case “inactive”
   * - count <= q33 => vert (calme)
   * - count <= q66 => orange (moyen)
   * - sinon => rouge (chaud), avec effet pulse si risque moyen élevé
   */
  const getColor = (risk: number, count: number) => {
    if (count === 0) return "bg-slate-800/50 border-slate-800 text-slate-600";

    if (count <= q33) return "bg-emerald-500/25 border-emerald-500/35 text-emerald-300";
    if (count <= q66) return "bg-amber-500/25 border-amber-500/35 text-amber-300";

    return risk >= 70
      ? "bg-red-500/25 border-red-500/35 text-red-300 shadow-[0_0_15px_rgba(239,68,68,0.25)] animate-pulse"
      : "bg-red-500/20 border-red-500/30 text-red-300 shadow-[0_0_10px_rgba(239,68,68,0.15)]";
  };

  return (
    <div className="h-full flex flex-col">
      {/* Grille 20 cases (5 colonnes x 4 lignes) */}
      <div className="flex-1 grid grid-cols-5 gap-2">
        {zoneStats.map((stat, idx) => (
          <div
            key={idx}
            className={`
              relative rounded flex flex-col items-center justify-center border text-[10px] font-mono cursor-help group transition-all duration-300
              ${getColor(stat.avgRisk, stat.count)}
            `}
          >
            {/* Numéro d’arrondissement */}
            <span className="font-bold">{idx + 1}</span>

            {/* Badge count */}
            {stat.count > 0 && (
              <span className="mt-1 text-[10px] font-bold opacity-90">{stat.count}</span>
            )}

            {/* Tooltip : visible uniquement au hover (group-hover) */}
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-44 bg-slate-800 border border-slate-600 p-3 rounded shadow-xl hidden group-hover:block z-20 text-center pointer-events-none">
              <div className="text-white font-bold mb-1">Paris {idx + 1}</div>

              {/*"Signalements" = count total calculé */}
              <div className="text-slate-300 text-[10px]">Signalements: {stat.count}</div>

              {/* Risque moyen affiché seulement si la zone a de l’activité */}
              {stat.count > 0 && (
                <div className="text-slate-400 text-[10px]">
                  Risque moy: {Math.round(stat.avgRisk)}/100
                </div>
              )}

              {/* Debug discret : rappelle les seuils dynamiques  */}
              {stat.count > 0 && (
                <div className="text-slate-500 text-[10px] mt-1">
                  seuils: ≤{Math.round(q33)} vert • ≤{Math.round(q66)} orange
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Légende visuelle */}
      <div className="mt-3 flex justify-between text-[10px] text-slate-500 font-medium">
        <span>Activité normale</span>
        <span>Signalements fréquents</span>
      </div>

      {/* Barre dégradée (simple repère visuel) */}
      <div className="h-1 w-full bg-gradient-to-r from-emerald-900/50 via-amber-900/50 to-red-900 rounded-full mt-1"></div>
    </div>
  );
};

export default ParisMap;
