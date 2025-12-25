"""
app

Package racine de l’application backend SentinelAI.

Rôle (fonctionnel) :
- Contient tout le code applicatif (API, logique métier, accès DB, ML, schémas).
- Sert de point d’ancrage pour les imports : `from app...`

Organisation (haute-level) :
- app.api      : routes FastAPI (contrats HTTP, dépendances, sérialisation)
- app.core     : briques transverses (settings, errors, logs, sécurité, realtime, rate-limit…)
- app.db       : base SQLAlchemy + session async
- app.models   : modèles ORM (tables Postgres)
- app.schemas  : schémas Pydantic (entrées/sorties API)
- app.services : logique métier / use-cases (scoring, dashboard…)
- app.ml       : inference + registry (chargement modèles, vectorization)


"""
