from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import joblib
import pandas as pd
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier
from sqlalchemy import create_engine, text

from app.core.settings import settings
from app.ml.feature_vectorizer import FeatureSpec, vectorize

"""
Script CLI: train_xgboost

Rôle (fonctionnel) :
- Entraîne un modèle supervisé XGBoost (XGBClassifier) à partir des transactions en base.
- Utilise un “pseudo-label” pour la démo : fraude = 1 si rs_score >= ALERT_THRESHOLD.
  (rs_score provient de risk_scores, donc ce script suppose que des scores existent déjà.)
- Transforme les inputs via FeatureSpec + vectorize() (même pipeline que runtime).
- Exporte un bundle .joblib versionné dans backend/models/ :
  - model (XGBClassifier)
  - spec (vocabulaires one-hot)
  - meta (kind, model_version, trained_at, règle de labeling)

Usage typique :
- Démo / PoC : on génère des transactions + risk_scores (seed + scoring),
  puis on apprend un modèle “IA” simple sur la base de ce signal.
- Le runtime chargera ensuite automatiquement le modèle le plus récent
  (priorité XGBoost, fallback IsolationForest).

Notes :
- Le pseudo-label n’est pas une vérité terrain : il sert à rendre la démo crédible et stable.
- Les rolling features ne sont pas calculées ici (supervisé simple) :
  on met 0, et vectorize() reste compatible avec l’inférence (train = inference).
- scale_pos_weight compense le déséquilibre (peu de “fraudes”).
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="v1", help="Tag de version (ex: v1, v2) pour le nom du modèle exporté")
    args = ap.parse_args()

    # Connexion DB sync (scripts)
    engine = create_engine(settings.DATABASE_URL_SYNC)

    # Dataset: transactions + score existant (pseudo-label)
    q = text("""
        SELECT
            t.id, t.occurred_at, t.amount, t.merchant_name, t.merchant_category,
            t.arrondissement, t.channel, t.is_online,
            COALESCE(rs.score, 0) AS rs_score
        FROM transactions t
        LEFT JOIN risk_scores rs ON rs.transaction_id = t.id
    """)
    df = pd.read_sql(q, engine)

    if df.empty:
        print("Aucune transaction en base. Seed avant d'entraîner.")
        return

    df["occurred_at"] = pd.to_datetime(df["occurred_at"], utc=True)
    df["hour"] = df["occurred_at"].dt.hour

    # Label supervisé de démo (pseudo-label)
    y = (df["rs_score"] >= settings.ALERT_THRESHOLD).astype(int)

    # Vocab (top-N) : one-hot + "other" (géré dans vectorize)
    cat_vocab = tuple(df["merchant_category"].fillna("unknown").str.lower().value_counts().head(12).index.tolist())
    ch_vocab = tuple(df["channel"].fillna("unknown").str.lower().value_counts().head(6).index.tolist())
    z_vocab = tuple(df["arrondissement"].fillna("unknown").str.lower().value_counts().head(12).index.tolist())
    spec = FeatureSpec(categories=cat_vocab, channels=ch_vocab, zones=z_vocab)

    # Vectorisation (train = inference)
    X = []
    for _, r in df.iterrows():
        feats = {
            "hour": int(r["hour"]),
            "amount": float(r["amount"]),
            "is_online": bool(r["is_online"]),

            # Supervisé simple : pas de rolling ici -> on fixe 0.
            # (vectorize() sait gérer ces champs, et l'inférence les fournit en vrai via FeatureBuilder)
            "merchant_tx_count_24h": 0,
            "avg_amount_category_7d": 0.0,

            "category": str(r["merchant_category"] or ""),
            "channel": str(r["channel"] or ""),
            "arrondissement": str(r["arrondissement"] or ""),
        }
        X.append(vectorize(feats, spec))

    # Split train/test avec stratify (répartition stable des classes)
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.25,
        random_state=42,
        stratify=y,
    )

    # Rebalancing (fraude rare)
    pos = int(y_train.sum())
    neg = int(len(y_train) - pos)
    scale_pos_weight = (neg / max(pos, 1))

    # Entraînement XGBoost
    model = XGBClassifier(
        n_estimators=250,
        max_depth=4,
        learning_rate=0.08,
        subsample=0.9,
        colsample_bytree=0.9,
        eval_metric="logloss",
        random_state=42,
        scale_pos_weight=scale_pos_weight,
    )
    model.fit(X_train, y_train)

    # Versioning artefact
    now = datetime.utcnow().strftime("%Y%m%d-%H%M")
    model_version = f"xgboost_{args.version}_{now}"

    # Sortie dans backend/models/
    out_dir = Path(__file__).resolve().parents[1] / "models"
    out_dir.mkdir(parents=True, exist_ok=True)

    bundle = {
        "model": model,
        "spec": {
            "categories": list(spec.categories),
            "channels": list(spec.channels),
            "zones": list(spec.zones),
        },
        "meta": {
            "kind": "xgboost",
            "model_version": model_version,
            "trained_at": now,
            "labeling": f"rs_score >= {settings.ALERT_THRESHOLD}",
        },
    }

    out_path = out_dir / f"{model_version}.joblib"
    joblib.dump(bundle, out_path)
    print("OK - saved:", out_path)


if __name__ == "__main__":
    main()
