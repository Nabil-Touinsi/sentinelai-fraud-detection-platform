"""
app.ml

Package “Machine Learning” (couche modèle) :
- Regroupe ce qui concerne le scoring / modèle de risque, côté application.
- Peut contenir :
  - chargement des artefacts (modèle, features, règles),
  - pré-traitements / feature engineering léger,
  - wrappers d’inférence (predict/score),
  - versioning et métadonnées modèle.

Note :
- Dans la version démo, une partie du scoring peut être simulée ou simplifiée,
  mais ce package sert de point d’ancrage si le modèle devient “réel” ensuite.
"""
