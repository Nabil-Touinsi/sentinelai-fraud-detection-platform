# SentinelAI — Backend (API)

Backend **FastAPI** pour la plateforme *SentinelAI* (détection de fraude / scoring + alertes).
Il expose des endpoints REST pour les **transactions**, le **scoring**, les **alertes**, et un flux **temps réel** via WebSocket.

---

## 1) Stack & principes

- **FastAPI** : API REST + docs Swagger (`/docs`)
- **SQLAlchemy (async)** : accès base de données
- **PostgreSQL** : stockage (transactions, scores, alertes, événements)
- **Alembic** : migrations DB (dossier `alembic/`)
- **WebSocket** : push d’événements côté UI (`/ws/alerts`)
- **Rate limiting** (optionnel) : protection basique côté API

✅ Le backend est pensé pour alimenter l’UI **sans mock** : Dashboard, Alerts, Transactions, Simulator.

---

## 2) Arborescence rapide

- `app/main.py` : création de l’app FastAPI + middlewares (CORS, erreurs, request_id…)
- `app/api/` : routes
  - `transactions.py` : CRUD/list transactions
  - `score.py` : scoring d’une transaction + création d’alerte si seuil atteint
  - `alerts.py` : liste + PATCH statut/commentaire
  - `dashboard.py` : agrégats KPI / séries / hotspots
  - `status.py` / `health.py` : état du système
  - `ws.py` : WebSocket alerts
- `app/models/` : modèles SQLAlchemy (Transaction, RiskScore, Alert, AlertEvent, …)
- `app/services/` : logique métier (scoring, etc.)
- `alembic/` : migrations (versions dans `alembic/versions/`)
- `scripts/` : scripts utilitaires (seed, train, score_one…)

---

## 3) Configuration (.env)

Le backend charge un fichier `.env` (voir `app/core/settings.py`).

Variables principales (noms attendus) :

- `ENV` : `dev` / `prod` …
- `DEBUG` : `true` / `false`
- `LOG_LEVEL` : `INFO` / `DEBUG` …
- `CORS_ORIGINS` : origines autorisées (ex: `http://localhost:3000,http://127.0.0.1:3000`)
- `API_KEY` : clé d’API (démo) si tu actives l’auth par header
- `DATABASE_URL` : URL async SQLAlchemy (Postgres)
- `DATABASE_URL_SYNC` : URL sync (utile Alembic/CLI)
- `ALERT_THRESHOLD` : seuil de déclenchement d’alerte (score >= threshold)
- `RATE_LIMIT_ENABLED` / `RATE_LIMIT_RPM` : rate limit (optionnel)

⚠️ Notes importantes :
- Le front envoie `X-API-Key` + `X-Actor` quand `auth: true` côté `apiFetch()`.
- Les endpoints “sensibles” peuvent exiger ces headers selon ta config.

---

## 4) Lancer en local

### 4.1 Pré-requis
- Python 3.10+ (recommandé)
- PostgreSQL (local) **ou** via Docker (si tu l’utilises déjà)

### 4.2 Installer les dépendances
Ce zip ne contient pas de `requirements.txt`/`pyproject.toml` visible.
Dans ton repo, tu as probablement déjà un fichier de dépendances à la racine.

Si tu dois installer “à la main”, la base minimale ressemble à :
- `fastapi`, `uvicorn`
- `sqlalchemy`, `asyncpg`
- `alembic`
- `pydantic-settings`

> Conseil : dans ton projet, garde un `requirements.txt` ou `pyproject.toml` pour rendre l’installation reproductible.

### 4.3 Démarrer l’API
Depuis le dossier backend (celui qui contient `app/` et `.env`) :

```bash
# (exemple) activer venv
python -m venv .venv
# Windows
.\.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

# démarrer l’API
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Ensuite :
- Swagger UI : `http://127.0.0.1:8000/docs`
- Health : `http://127.0.0.1:8000/health`

---

## 5) Base de données & migrations (Alembic)

### 5.1 Vérifier la config Alembic
- `alembic.ini` : config générale
- `alembic/env.py` : récupération de `DATABASE_URL_SYNC`

### 5.2 Appliquer les migrations
```bash
alembic upgrade head
```

### 5.3 Créer une nouvelle migration
```bash
alembic revision -m "ma_migration"
# ou autogenerate si config OK
alembic revision --autogenerate -m "describe_change"
```

---

## 6) Endpoints principaux (côté produit)

### Transactions
- `GET /transactions?page=1&page_size=...`
- `POST /transactions` : crée une transaction (utilisé par le Simulator)

### Scoring + alerte
- `POST /score` `{ "transaction_id": "<uuid>" }`
  - renvoie `score`, `risk_level`, `factors`, `threshold`
  - ✅ crée une **alerte** si `score >= ALERT_THRESHOLD`

### Alertes
- `GET /alerts?page=1&page_size=...`
- `PATCH /alerts/{id}` `{ "status": "...", "comment": "..." }`
  - ✅ règle backend : **commentaire requis** quand statut = `CLOTURE`

### Dashboard
- `GET /dashboard/summary?days=30&top_n=8`
  - `kpis` : volumes + alertes + score moyen (fenêtre)
  - `series.days[]` : série temporelle (graph)
  - `hotspots.arrondissements[]` : pour la heatmap ParisMap

### Status
- `GET /system/status` : état DB / WS / seuil / version éventuelle

---

## 7) Temps réel (WebSocket)

- WS : `GET ws://<API_BASE>/ws/alerts`

Événements typiques consommés par le front :
- `ALERT_CREATED`
- `ALERT_STATUS_CHANGED`
- `SCORE_COMPUTED`

✅ Le front a un fallback “polling” si WS down.

---

## 8) Headers utiles (observabilité)

Le front envoie automatiquement via `frontend/services/api.ts` :
- `X-Request-Id` : corrélation logs
- `X-API-Key` : si `auth: true`
- `X-Actor` : “qui agit” (ex: `admin-demo`)

---

## 9) Scripts utiles

Dans `scripts/` (selon ton usage) :
- `seed_demo.py` : injecter des données de démo
- `score_one.py` : scorer une transaction spécifique
- `train_iforest.py` / `train_xgboost.py` : entraînement (si tu gardes ces pistes)

> Le nom exact des paramètres dépend de ton implémentation : ouvre les scripts pour voir les options.

---

## 10) Checklist de debug rapide

- `/health` OK ?
- `/system/status` remonte bien DB/WS ?
- `GET /alerts?page=1&page_size=1` renvoie `data[]` + `meta` ?
- Le front a bien `VITE_API_URL=http://127.0.0.1:8000` ?
- Si `auth` activé : `VITE_API_KEY` + `VITE_ACTOR` bien renseignés côté front ?

---

### Licence / statut
Projet pédagogique/démo : l’auth et le scoring sont simplifiés, mais l’API est structurée comme une base “production-like” (migrations, événements, WS, status).
