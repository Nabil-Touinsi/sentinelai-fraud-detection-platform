# SentinelAI – Features ML (train = inference)

Toutes les features utilisées en ML sont produites par `FeatureBuilder`
et transformées par `app/ml/feature_vectorizer.py`.

## Numériques
- hour (0–23)
- amount
- is_online (0/1)
- merchant_tx_count_24h
- avg_amount_category_7d (0 si inconnu)

## Catégorielles (one-hot + "other")
- category (merchant_category)
- channel
- arrondissement (zone)
