// frontend/services/gemini.ts
import { FullTransactionData } from "../types";

/**
 * Service "Gemini" (mode démo)
 *
 * Rôle :
 * - Fournir une explication “humaine” et une recommandation d’action à partir d’une transaction.
 * - ✅ Ici c’est volontairement un générateur de texte local (pas d’appel réseau).
 *
 * Règles produit (inchangées) :
 * - score >= 80 : action forte
 * - score >= 60 : vérification approfondie
 * - sinon : surveillance simple
 */

function pick<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

/**
 * optionnel : rend le choix “stable” pour une même tx (pas de phrase qui change à chaque clic)
 * - si tu préfères du random pur, supprime stablePick et utilise pick()
 */
function stablePick<T>(arr: T[], seed: string): T {
  let h = 2166136261;
  for (let i = 0; i < seed.length; i++) {
    h ^= seed.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  const idx = Math.abs(h) % arr.length;
  return arr[idx];
}

function buildActionText(score: number, seed: string) {
  const actionsCritical = [
    "Action : contacter le client immédiatement et suspendre la carte en cas de doute.",
    "Action : ouvrir une investigation prioritaire et déclencher une validation manuelle.",
    "Action : escalader au niveau fraude et lancer une vérification renforcée.",
    "Action : bloquer temporairement le moyen de paiement et confirmer l’identité du porteur.",
    "Action : appeler le client, vérifier l’historique, puis geler l’opération si incohérence.",
    "Action : initier une revue KYC/AML rapide et tracer l’incident dans le dossier.",
    "Action : vérifier l’adresse IP / canal / device (si dispo) et mettre en attente.",
    "Action : appliquer une mesure conservatoire (hold) et exiger une confirmation explicite.",
    "Action : marquer en “critique”, notifier l’équipe et suivre jusqu’à clôture.",
    "Action : contrôler les opérations similaires récentes et isoler la transaction si suspicion.",
  ];

  const actionsVerify = [
    "Action : vérifier l’historique récent et confirmer la cohérence avec le profil.",
    "Action : contrôler les transactions voisines (montant, fréquence, zone) avant décision.",
    "Action : demander une validation manuelle si la récurrence semble anormale.",
    "Action : comparer avec les habitudes (catégorie, horaire) et documenter la vérification.",
    "Action : contacter le client si un second signal apparaît dans la même fenêtre.",
    "Action : regarder les transactions des 24h et confirmer l’absence de pattern frauduleux.",
    "Action : mettre en enquête légère et surveiller les prochains événements.",
    "Action : vérifier le marchand (réputation / type) et confirmer la légitimité du paiement.",
    "Action : vérifier si l’achat est “online” + montant élevé relatif, puis décider escalade.",
    "Action : consigner un commentaire d’analyse et garder sous observation renforcée.",
  ];

  const actionsMonitor = [
    "Action : surveiller, aucune escalade immédiate.",
    "Action : continuer le suivi normal, pas d’action requise à ce stade.",
    "Action : garder en observation, recontrôler si un nouveau signal apparaît.",
    "Action : archiver en “OK”, avec contrôle automatique sur les prochaines opérations.",
    "Action : pas d’intervention, mais conserver un indicateur pour détection de répétition.",
    "Action : laisser passer, et réévaluer si la fréquence augmente sur 24h.",
    "Action : statut normal, monitoring standard.",
    "Action : vérifier rapidement la cohérence (catégorie/zone), puis clôturer si stable.",
    "Action : aucun blocage, uniquement supervision.",
    "Action : pas d’alerte opérateur, uniquement suivi système.",
  ];

  // ✅ choix stable (tu peux switch en pick(...) si tu préfères du random)
  if (score >= 80) return stablePick(actionsCritical, seed);
  if (score >= 60) return stablePick(actionsVerify, seed);
  return stablePick(actionsMonitor, seed);
}

function buildWhyText(tx: FullTransactionData, seed: string) {
  const factors = (tx.risk?.factors ?? []).slice(0, 3).filter(Boolean);

  // Si facteurs -> on fait une phrase courte et claire
  if (factors.length) {
    const templates = [
      `Facteurs détectés : ${factors.join(", ")}.`,
      `Le score s’appuie sur : ${factors.join(", ")}.`,
      `Signaux contributifs : ${factors.join(", ")}.`,
      `Indices relevés : ${factors.join(", ")}.`,
      `Éléments notables : ${factors.join(", ")}.`,
    ];
    return stablePick(templates, seed);
  }

  // Fallback sans facteurs 
  const generic = [
    "Le pattern observé (montant, horaire, lieu ou type de commerce) est atypique.",
    "La combinaison montant/canal/horaire s’écarte des habitudes attendues.",
    "Le comportement sort du profil classique et justifie une attention accrue.",
    "L’opération présente une signature inhabituelle sur la période récente.",
    "La transaction est statistiquement moins fréquente pour ce type de contexte.",
  ];
  return stablePick(generic, seed);
}

export const explainRiskWithGemini = async (tx: FullTransactionData): Promise<string> => {
  const score = tx.risk?.score ?? 0;

  const hour = new Date(tx.timestamp).toLocaleTimeString();

  //
  const seed = String((tx as any).id ?? `${tx.merchant_name}-${tx.amount}-${tx.timestamp}`);

  const why = buildWhyText(tx, seed);
  const action = buildActionText(score, seed);

  return `Mode démo — ${tx.merchant_name} (${tx.merchant_category}), ${tx.amount}€ à ${hour} (Paris ${tx.zone_paris}e), score ${score}/100. ${why} ${action}`;
};
