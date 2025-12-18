import { useCallback, useEffect, useState } from "react";
import { useAlertsRealtime } from "../hooks/useAlertsRealtime";

const API = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export default function Alerts() {
  const [alerts, setAlerts] = useState([]);

  const fetchAlerts = useCallback(async () => {
    const res = await fetch(`${API}/alerts?limit=50&sort=created_at:desc`);
    const data = await res.json();
    setAlerts(data.items ?? data); // selon ton format
  }, []);

  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts]);

  useAlertsRealtime({
    apiBaseUrl: API,
    fallbackPoll: fetchAlerts,
    onEvent: (evt) => {
      if (evt?.type === "ALERT_CREATED" || evt?.type === "ALERT_UPDATED") {
        fetchAlerts();
      }
    },
  });

  return (
    <div>
      <h1>Alertes</h1>
      {/* ton tableau */}
      <pre>{JSON.stringify(alerts, null, 2)}</pre>
    </div>
  );
}
