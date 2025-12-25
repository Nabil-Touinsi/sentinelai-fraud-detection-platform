import { FullTransactionData } from "../types";

export const explainRiskWithGemini = async (
  tx: FullTransactionData
): Promise<string> => {
  const score = tx.risk?.score ?? 0;
  const factors = (tx.risk?.factors ?? []).slice(0, 3).join(", ");
  const hour = new Date(tx.timestamp).toLocaleTimeString();

  // Explication courte, stable, sans dépendance externe
  const why =
    factors
      ? `Facteurs détectés : ${factors}.`
      : `Le pattern observé (montant, horaire, lieu ou type de commerce) est atypique.`;

  const action =
    score >= 80
      ? "Action : appeler le client et bloquer temporairement si doute."
      : score >= 60
      ? "Action : vérifier l’historique et confirmer la légitimité."
      : "Action : surveiller, pas d’escalade immédiate.";

  return `Mode démo — ${tx.merchant_name} (${tx.merchant_category}), ${tx.amount}€ à ${hour} (Paris ${tx.zone_paris}e), score ${score}/100. ${why} ${action}`;
};
