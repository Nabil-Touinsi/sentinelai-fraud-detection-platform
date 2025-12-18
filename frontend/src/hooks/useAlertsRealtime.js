import { useEffect, useRef } from "react";

export function useAlertsRealtime({ apiBaseUrl, onEvent, fallbackPoll }) {
  const wsRef = useRef(null);
  const pollRef = useRef(null);

  useEffect(() => {
    const wsUrl = apiBaseUrl.replace("http", "ws") + "/ws/alerts";
    let wsOk = false;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        wsOk = true;
        // petit ping pour maintenir la connexion
        ws.send("PING");
      };

      ws.onmessage = (msg) => {
        try {
          const evt = JSON.parse(msg.data);
          onEvent?.(evt);
        } catch (_) {}
      };

      ws.onerror = () => {
        wsOk = false;
      };

      ws.onclose = () => {
        // fallback polling si WS KO
        if (!wsOk && fallbackPoll) {
          pollRef.current = setInterval(() => fallbackPoll(), 7000);
        }
      };
    } catch (e) {
      if (fallbackPoll) {
        pollRef.current = setInterval(() => fallbackPoll(), 7000);
      }
    }

    return () => {
      if (wsRef.current) wsRef.current.close();
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [apiBaseUrl, onEvent, fallbackPoll]);
}
