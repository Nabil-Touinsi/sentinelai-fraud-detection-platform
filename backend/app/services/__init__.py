"""
app.services

Package “services” : logique applicative (use-cases) indépendante des endpoints HTTP.

Rôle (fonctionnel) :
- Contient les services qui orchestrent :
  - accès DB (via sessions),
  - scoring / logique métier,
  - création/mise à jour d’entités (ex : RiskScore, Alert, AlertEvent),
  - règles métier réutilisables (hors couche API).

Principe :
- app.api = transport HTTP (routes, validation, dépendances)
- app.services = orchestration métier (réutilisable, testable)
- app.models / app.schemas = persistance et contrats
"""
