# Sentinel — Frontend (React + Vite)

Ce dossier contient l’interface web **Sentinel** (tableau de bord, transactions, alertes, démo).
L’UI consomme l’API FastAPI via `VITE_API_URL` et peut fonctionner en **temps réel** (WebSocket) avec un **fallback polling**.

---

## 1) Prérequis

- Node.js 18+ recommandé
- Backend Sentinel démarré (FastAPI), par défaut sur `http://127.0.0.1:8000`

---

## 2) Installation

Depuis le dossier `frontend/` :

```bash
npm install
```

---

## 3) Configuration (.env.local)

Créer (ou vérifier) `frontend/.env.local` :

```env
VITE_API_URL=http://127.0.0.1:8000
VITE_API_KEY=... (optionnel selon ton backend)
VITE_ACTOR=admin-demo
```

### Variables utilisées

- `VITE_API_URL` : **source unique** pour l’URL API (sert aussi à déduire la base WS).
- `VITE_API_KEY` : clé API si les endpoints protégés l’exigent.
- `VITE_ACTOR` : identité “métier” envoyée via `X-Actor` (audits / logs).

---

## 4) Lancer le front

```bash
npm run dev
```

Par défaut, Vite écoute sur :

- `http://localhost:3000` (voir `vite.config.ts`)

> Le serveur Vite est configuré avec `host: 0.0.0.0` pour pouvoir tester depuis un autre device si besoin.

---

## 5) Pages / Routes

Les routes sont déclarées dans `frontend/App.tsx` :

- `/` : **Dashboard** (KPIs + graphe + ParisMap)
- `/transactions` : **Transactions**
- `/alerts` : **Alertes**
- `/simulator` : **Démo / Simulator** (injection de transactions réelles + scoring)

---

## 6) Architecture rapide

### 6.1 Services

- `services/api.ts`
  - Wrapper `apiFetch()` : gère `X-Request-Id`, JSON, erreurs normalisées, headers `X-API-Key` / `X-Actor` (si `auth: true`).
- `services/realtime.ts`
  - Petit helper WS (utilisé/optionnel selon pages).
- `services/gemini.ts`
  - Texte “pédagogique” côté UI (mode démo) basé sur le contenu `risk`.

### 6.2 Types

- `types.ts`
  - Types alignés backend : `Transaction`, `RiskScore`, `Alert`, `AlertStatus`, etc.
  - Helpers robustes : normalisation de statut, labels/couleurs UI.

### 6.3 Composants

- `components/ParisMap.tsx`
  - Grille 1..20 (arrondissements) : **couleur = volume de signalements**, **pulse = risque élevé**.
  - Seuils dynamiques via quantiles (q33/q66) pour garder un rendu lisible même si les volumes changent.

---

## 7) Temps réel (WebSocket) + fallback

- Page `Alerts.tsx` :
  - Essaie de se connecter à `${wsBase}/ws/alerts`.
  - Si WS indisponible → passe en **Polling** toutes les `POLL_MS` (ex: 7s).
  - À réception d’événements (`ALERT_CREATED`, `ALERT_STATUS_CHANGED`, `SCORE_COMPUTED`) → refresh de la liste.

---

## 8) Notes produit (pour comprendre l’UI)

- “Signalements” = nombre d’occurrences (souvent `count`) agrégées par zone/catégorie.
- “Risque” = score 0..100 (ou 0..1 dans certains flux) :
  - Les helpers UI normalisent pour éviter les incohérences.
- Les fallbacks sont assumés :
  - Ex : sur la carte, s’il y a peu de données, les quantiles utilisent des valeurs par défaut.

---

## 9) Dépannage rapide

### L’UI n’affiche rien / erreurs réseau
- Vérifie que le backend répond : `GET http://127.0.0.1:8000/system/status`
- Vérifie `VITE_API_URL` dans `.env.local`
- Relance Vite après modification des variables :
  ```bash
  npm run dev
  ```

### WebSocket ne se connecte pas
- L’UI bascule automatiquement en polling.
- Vérifie que le backend expose bien `GET/WS /ws/alerts`.

---

## 10) Scripts utiles

```bash
npm run dev      # serveur de dev
npm run build    # build prod
npm run preview  # preview du build
```
