from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import IsolationForest
from sqlalchemy import create_engine, text

from app.core.settings import settings
from app.ml.feature_vectorizer import FeatureSpec, vectorize

"""
Script CLI: train_iforest

Rôle (fonctionnel) :
- Entraîne un modèle d’anomaly detection (IsolationForest) à partir des transactions en base.
- Reproduit les mêmes features “train = inference” :
  - features numériques (hour, amount, is_online, merchant_tx_count_24h, avg_amount_category_7d)
  - one-hot sur category / channel / arrondissement via FeatureSpec + vectorize()
- Exporte un bundle .joblib versionné dans backend/models/ :
  - model (IsolationForest)
  - spec (vocabulaires one-hot)
  - meta (kind, model_version, trained_at, calibration q05/q95)

Usage typique :
- Après un seed demo (transactions en base), pour produire un modèle local.
- Permet au runtime (app/ml/model_registry.py + app/ml/inference.py) de charger le dernier modèle dispo.

Notes :
- Le modèle est non supervisé (pas de label fraude).
- La calibration q05/q95 sert à convertir decision_function -> score 0..100 en prod.
- Le vocabulaire est “top-N” + fallback implicite “other” dans vectorize().
"""


def build_rolling_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Construit des features “contextuelles” sur fenêtres glissantes :
- merchant_tx_count_24h : fréquence 24h par marchand
- avg_amount_category_7d : moyenne 7 jours par catégorie

Anti-NaN :
- Remplit les valeurs manquantes pour éviter d'entraîner sur des NaN.
    """
    df = df.sort_values("occurred_at").copy()
    df["occurred_at"] = pd.to_datetime(df["occurred_at"], utc=True)

    # rolling count 24h par merchant
    s = (
        df.set_index("occurred_at")
          .groupby("merchant_name")["id"]
          .rolling("24h")
          .count()
          .reset_index(level=0, drop=True)
    )
    df["merchant_tx_count_24h"] = s

    # rolling mean 7j par category
    m = (
        df.set_index("occurred_at")
          .groupby("merchant_category")["amount"]
          .rolling("7D")
          .mean()
          .reset_index(level=0, drop=True)
    )
    df["avg_amount_category_7d"] = m

    # anti-NaN
    df["merchant_tx_count_24h"] = df["merchant_tx_count_24h"].fillna(0).astype(int)
    df["avg_amount_category_7d"] = df["avg_amount_category_7d"].fillna(0.0).astype(float)

    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="v1", help="Tag de version (ex: v1, v2) pour le nom du modèle exporté")
    args = ap.parse_args()

    # Connexion DB sync (scripts)
    engine = create_engine(settings.DATABASE_URL_SYNC)

    # Lecture des transactions brutes
    q = text("""
        SELECT id, occurred_at, amount, currency, merchant_name, merchant_category,
               arrondissement, channel, is_online
        FROM transactions
    """)
    df = pd.read_sql(q, engine)

    if df.empty:
        print("Aucune transaction en base. Seed avant d'entraîner.")
        return

    # Features de base
    df["hour"] = pd.to_datetime(df["occurred_at"], utc=True).dt.hour
    df = build_rolling_features(df)

    # Vocab (top-N) : encodeur one-hot + "other" (géré dans vectorize)
    cat_vocab = tuple(df["merchant_category"].fillna("unknown").str.lower().value_counts().head(12).index.tolist())
    ch_vocab = tuple(df["channel"].fillna("unknown").str.lower().value_counts().head(6).index.tolist())
    z_vocab = tuple(df["arrondissement"].fillna("unknown").str.lower().value_counts().head(12).index.tolist())

    spec = FeatureSpec(categories=cat_vocab, channels=ch_vocab, zones=z_vocab)

    # Vectorisation (mêmes règles que runtime)
    X = []
    for _, r in df.iterrows():
        feats = {
            "hour": int(r["hour"]),
            "amount": float(r["amount"]),
            "is_online": bool(r["is_online"]),
            "merchant_tx_count_24h": int(r["merchant_tx_count_24h"]),
            "avg_amount_category_7d": float(r["avg_amount_category_7d"]) if pd.notna(r["avg_amount_category_7d"]) else 0.0,
            "category": str(r["merchant_category"] or ""),
            "channel": str(r["channel"] or ""),
            "arrondissement": str(r["arrondissement"] or ""),
        }
        X.append(vectorize(feats, spec))

    # Entraînement IF (anomaly detection)
    model = IsolationForest(
        n_estimators=200,
        contamination=0.05,
        random_state=42,
    )
    model.fit(X)

    # Calibration simple : decision_function -> anomaly -> normalisation 0..100
    scores = model.decision_function(X)
    anomaly = (-scores)
    q05 = float(pd.Series(anomaly).quantile(0.05))
    q95 = float(pd.Series(anomaly).quantile(0.95))

    # Versioning artefact
    now = datetime.utcnow().strftime("%Y%m%d-%H%M")
    model_version = f"iforest_{args.version}_{now}"

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
            "kind": "iforest",
            "model_version": model_version,
            "trained_at": now,
            "q05": q05,
            "q95": q95,
        },
    }

    out_path = out_dir / f"{model_version}.joblib"
    joblib.dump(bundle, out_path)
    print("OK - saved:", out_path)


if __name__ == "__main__":
    main()
