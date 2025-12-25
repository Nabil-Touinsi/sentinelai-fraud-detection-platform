# SentinelAI – Features ML (train = inference)

Ce document décrit le **contrat de features** utilisé par le pipeline ML, avec une règle clé :
**les mêmes features (mêmes noms, mêmes transformations) doivent être utilisées à l’entraînement et en production**.

Source de vérité :
- Construction des features : `app/services/feature_builder.py`
- Vectorisation (one-hot + ordre des colonnes) : `app/ml/feature_vectorizer.py`

Pourquoi c’est important :
- Garantit que **train == inference** (pas de “data drift” lié au code).
- Évite les bugs silencieux : colonnes manquantes, ordre différent, encodage non aligné.

---

## Features numériques

Ces features sont ajoutées telles quelles (après conversion en float/int si besoin).

- **hour** *(0–23)*  
  Heure de la transaction (extrait de `occurred_at`).

- **amount**  
  Montant de la transaction.

- **is_online** *(0/1)*  
  Indique si la transaction est en ligne.

- **merchant_tx_count_24h**  
  Nombre de transactions du même marchand sur les dernières 24h  
  *(proxy de répétition / burst d’activité)*.

- **avg_amount_category_7d** *(0 si inconnu)*  
  Montant moyen observé sur 7 jours pour la catégorie de marchand  
  *(proxy de “montant habituel” par catégorie)*.

---

## Features catégorielles (one-hot + “other”)

Ces champs sont encodés en **one-hot** via un vocabulaire fixé (FeatureSpec).  
Si une valeur n’est pas connue du vocabulaire, elle tombe dans la case **other**.

- **category** *(= merchant_category)*  
- **channel**  
- **arrondissement** *(= zone)*

Notes :
- Les valeurs sont normalisées en `lower()` avant encodage.
- Le vecteur one-hot a **(len(vocab) + 1)** dimensions pour inclure **other**.

---

## Rappel : contrat “train = inference”

Pour éviter toute divergence :
- On ne calcule pas de features ML ailleurs que dans `FeatureBuilder`.
- On ne modifie pas l’ordre/format de vectorisation ailleurs que dans `feature_vectorizer.py`.
- Toute nouvelle feature doit être ajoutée **des deux côtés** (builder + vectorizer + spec).
