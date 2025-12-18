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


def build_rolling_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("occurred_at").copy()
    df["occurred_at"] = pd.to_datetime(df["occurred_at"], utc=True)

    # Rolling count 24h par merchant
    s = (
        df.set_index("occurred_at")
          .groupby("merchant_name")["id"]
          .rolling("24h")
          .count()
          .reset_index(level=0, drop=True)
    )
    df["merchant_tx_count_24h"] = s

    # Rolling mean 7j par category
    m = (
        df.set_index("occurred_at")
          .groupby("merchant_category")["amount"]
          .rolling("7D")
          .mean()
          .reset_index(level=0, drop=True)
    )
    df["avg_amount_category_7d"] = m

    # ✅ anti-NaN
    df["merchant_tx_count_24h"] = df["merchant_tx_count_24h"].fillna(0).astype(int)
    df["avg_amount_category_7d"] = df["avg_amount_category_7d"].fillna(0.0).astype(float)

    return df



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="v1")
    args = ap.parse_args()

    engine = create_engine(settings.DATABASE_URL_SYNC)

    q = text("""
        SELECT id, occurred_at, amount, currency, merchant_name, merchant_category,
               arrondissement, channel, is_online
        FROM transactions
    """)
    df = pd.read_sql(q, engine)

    if df.empty:
        print("Aucune transaction en base. Seed avant d'entraîner.")
        return

    df["hour"] = pd.to_datetime(df["occurred_at"], utc=True).dt.hour
    df = build_rolling_features(df)

    # vocab (top 12) + other
    cat_vocab = tuple(df["merchant_category"].fillna("unknown").str.lower().value_counts().head(12).index.tolist())
    ch_vocab = tuple(df["channel"].fillna("unknown").str.lower().value_counts().head(6).index.tolist())
    z_vocab = tuple(df["arrondissement"].fillna("unknown").str.lower().value_counts().head(12).index.tolist())

    spec = FeatureSpec(categories=cat_vocab, channels=ch_vocab, zones=z_vocab)

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

    model = IsolationForest(
        n_estimators=200,
        contamination=0.05,
        random_state=42,
    )
    model.fit(X)

    # calibration simple pour convertir decision_function en 0..100
    scores = model.decision_function(X)
    anomaly = (-scores)
    q05 = float(pd.Series(anomaly).quantile(0.05))
    q95 = float(pd.Series(anomaly).quantile(0.95))

    now = datetime.utcnow().strftime("%Y%m%d-%H%M")
    model_version = f"iforest_{args.version}_{now}"

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
