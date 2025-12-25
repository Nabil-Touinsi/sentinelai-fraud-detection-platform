import path from "path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

/**
 * vite.config.ts
 *
 * Rôle :
 * - Configuration Vite pour le front Sentinel (React).
 * - Définit le serveur de dev (port/host) et les alias d’import.
 *
 * Entrées :
 * - Variables d’environnement côté front (VITE_*) sont lues ailleurs (services/api.ts).
 *
 * Sorties :
 * - Serveur de dev accessible sur le réseau local (host 0.0.0.0)
 * - Résolution d’imports simplifiée via alias "@"
 *
 * Hypothèses / intent :
 * - Port 3000 choisi pour coller à un usage “app web” (et éviter certains ports déjà pris).
 * - Host 0.0.0.0 permet d’ouvrir l’UI depuis un autre appareil (VM, téléphone, etc.) si besoin.
 */

export default defineConfig({
  server: {
    port: 3000,
    host: "0.0.0.0",
  },
  plugins: [react()],
  resolve: {
    alias: {
      //  Alias local : "@/<fichier>" pointe vers la racine du dossier frontend
      // Exemple: import x from "@/services/api"
      "@": path.resolve(__dirname, "."),
    },
  },
});
