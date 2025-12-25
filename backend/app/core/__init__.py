"""
app.core

Package “cœur” de l’application : il regroupe tout ce qui est transversal (cross-cutting concerns),
c’est-à-dire ce qui s’applique à plusieurs endpoints/services et qui ne dépend pas d’un domaine métier
spécifique (transactions, alertes, scoring, etc.).

On y trouve typiquement :

- settings
  Centralise la configuration (variables d’environnement, seuils, flags, version du modèle, URLs, etc.).
  Objectif : éviter les “constantes” dispersées dans le code.

- errors
  Définit un format d’erreur API uniforme (code, message, status, request_id, timestamp) et des
  exceptions applicatives (ex : AppHTTPException) pour garantir des réponses cohérentes.

- logging
  Configure les logs (format, niveau, handlers) et les enrichit si besoin (request_id, contexte).
  Objectif : diagnostiquer facilement en dev/prod.

- request_id
  Génère/attache un identifiant de requête (correlation id) pour tracer une requête de bout en bout
  (utile quand on a plusieurs services, ou du temps réel).

- rate_limit
  Contient la logique de limitation de débit (protection anti-spam / anti-abus) et/ou middleware associé.

- realtime
  Contient le “manager” WebSocket (connexion/déconnexion, broadcast) et l’infrastructure temps réel
  utilisée par les endpoints (ex : /score qui push des events au dashboard).

En résumé :
- app.core = infrastructure + conventions (config, logs, erreurs, middlewares, temps réel)
- app.api / app.services / app.models = logique métier + endpoints + persistance
"""
