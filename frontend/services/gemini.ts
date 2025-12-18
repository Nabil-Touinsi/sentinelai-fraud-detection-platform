import { GoogleGenAI } from "@google/genai";
import { FullTransactionData } from "../types";

export const explainRiskWithGemini = async (tx: FullTransactionData): Promise<string> => {
  if (!process.env.API_KEY) {
    return `Mode démo : Analyse du dossier ${tx.merchant_name}. Le montant de ${tx.amount}€ apparaît atypique pour la catégorie ${tx.merchant_category}, surtout combiné à l'horaire de la transaction.`;
  }

  try {
    const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });
    
    const prompt = `
      Tu es un expert mentor en détection de fraude bancaire. Tu t'adresses à un analyste junior.
      
      Contexte transaction :
      - Enseigne : ${tx.merchant_name} (Catégorie: ${tx.merchant_category})
      - Montant : ${tx.amount} EUR
      - Paiement : ${tx.payment_method}
      - Heure : ${new Date(tx.timestamp).toLocaleTimeString()}
      - Lieu : Paris ${tx.zone_paris}ème
      - Score Risque : ${tx.risk?.score}/100
      - Raisons techniques identifiées : ${tx.risk?.factors.join(', ')}
      
      Objectif :
      Explique en 2 phrases simples et pédagogiques pourquoi cette transaction spécifique chez ${tx.merchant_name} est signalée. Sois concret (parle du type de commerce).
      Donne une action recommandée (Appeler le client, Vérifier les précédents, Clôturer).
    `;

    const response = await ai.models.generateContent({
      model: 'gemini-2.5-flash',
      contents: prompt,
    });

    return response.text || "Analyse indisponible.";
  } catch (error) {
    console.error("Gemini Error:", error);
    return "Le service d'aide à la décision est temporairement indisponible.";
  }
};