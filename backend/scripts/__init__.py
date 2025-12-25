"""
scripts

Package utilitaire pour les scripts de maintenance / data / ML.

Rôle (fonctionnel) :
- Contient des scripts exécutables (CLI) liés au projet, par exemple :
  - entraînement / export de modèles ML
  - génération de données (seed, simulation)
  - tâches ponctuelles de debug / migration / inspection

Pourquoi un __init__.py :
- Permet à Python de traiter `scripts/` comme un package.
- Facilite certains imports quand un script réutilise du code applicatif (`from app...`).

Note :
- Les scripts ne doivent pas contenir de logique métier “centrale” :
  ils orchestrent et appellent les modules de `app/` (services, ml, db…).
"""
