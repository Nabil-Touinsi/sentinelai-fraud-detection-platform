export function connectAlertsWS(apiBaseUrl: string, onEvent: (evt: any) => void) {
  const wsUrl = apiBaseUrl.replace(/^http/, "ws") + "/ws/alerts";
  const ws = new WebSocket(wsUrl);

  ws.onmessage = (m) => {
    try {
      onEvent(JSON.parse(m.data));
    } catch {
      // ignore
    }
  };

  return ws;
}
