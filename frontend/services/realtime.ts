// frontend/services/realtime.ts

/**
 * realtime.ts
 *
 * Rôle :
 * - Centraliser la connexion WebSocket “alertes” côté frontend.
 * - Permettre à l’UI (Dashboard / Alerts) de se rafraîchir dès qu’un événement arrive,
 *   sans attendre le polling.
 *
 * Données attendues :
 * - apiBaseUrl : base HTTP de l’API (ex: http://127.0.0.1:8000 ou https://prod.example.com)
 * - onEvent(evt) : callback appelé à chaque message WS parsé en JSON
 *
 * Sortie :
 * - WebSocket : instance native, que l’appelant peut fermer (ws.close()).
 *
 * Hypothèses importantes :
 * - Le backend expose un endpoint WS à : /ws/alerts
 * - Les messages reçus sont des JSON (sinon on ignore silencieusement)
 *
 * ✅ Produit :
 * - Les événements WS servent uniquement de “signal” (quelque chose a changé),
 *   l’UI peut ensuite refetch la liste via HTTP pour rester source de vérité.
 */

export function connectAlertsWS(apiBaseUrl: string, onEvent: (evt: any) => void) {
  /**
   * wsUrl
   * - Convertit la base HTTP -> WS (http -> ws, https -> wss)
   * - Concatène le chemin standard des alertes.
   */
  const wsUrl = apiBaseUrl.replace(/^http/, "ws") + "/ws/alerts";
  const ws = new WebSocket(wsUrl);

  /**
   * onmessage
   * - On parse le payload en JSON
   * - Si parsing impossible -> on ignore (évite de casser l’UI sur un message bruité)
   */
  ws.onmessage = (m) => {
    try {
      onEvent(JSON.parse(m.data));
    } catch {
      // ignore
    }
  };

  return ws;
}
