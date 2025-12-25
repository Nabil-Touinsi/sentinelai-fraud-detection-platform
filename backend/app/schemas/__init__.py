"""
app.schemas

Package des schémas API (Pydantic).

Rôle (fonctionnel) :
- Définit les modèles d’entrée/sortie utilisés par l’API (request/response).
- Sépare clairement :
  - les modèles ORM (app.models) = persistance DB
  - les schémas Pydantic (app.schemas) = contrat HTTP / validation

Usage :
- Les endpoints FastAPI déclarent response_model=... et valident les payloads avec ces schémas.
- Les schémas peuvent exposer uniquement les champs nécessaires (pas forcément tous ceux de la DB).
"""
