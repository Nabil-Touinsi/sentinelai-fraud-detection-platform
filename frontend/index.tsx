// frontend/index.tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

/**
 * index.tsx
 *
 * Rôle :
 * - Point d’entrée du frontend (bootstrap React).
 * - Monte l’application dans la div #root définie dans index.html.
 *
 * Données attendues :
 * - Un élément DOM avec l’id "root" dans index.html.
 *
 * Sortie :
 * - Rend <App /> (routing + layout + pages).
 *
 *  Pourquoi ce guard :
 * - Si index.html est modifié (id différent, root supprimé), on échoue tôt
 *   avec une erreur claire plutôt qu’une page blanche silencieuse.
 */
const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error('Could not find root element to mount to');
}

const root = ReactDOM.createRoot(rootElement);
root.render(<App />);
