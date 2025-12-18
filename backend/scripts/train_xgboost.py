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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="v1")
    args = ap.parse_args()

    engine = create_engine(settings.DATABASE_URL_SYNC)

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

    # label supervisé: "fraude" si score >= seuil (pseudo-label)
    y = (df["rs_score"] >= settings.ALERT_THRESHOLD).astype(int)

    # vocab depuis dataset
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
            # Pas de rolling ici (supervisé simple) -> on met 0 (train=inference OK car vectorize gère)
            "merchant_tx_count_24h": 0,
            "avg_amount_category_7d": 0.0,
            "category": str(r["merchant_category"] or ""),
            "channel": str(r["channel"] or ""),
            "arrondissement": str(r["arrondissement"] or ""),
        }
        X.append(vectorize(feats, spec))

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)

    pos = int(y_train.sum())
    neg = int((len(y_train) - pos))
    scale_pos_weight = (neg / max(pos, 1))

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

    now = datetime.utcnow().strftime("%Y%m%d-%H%M")
    model_version = f"xgboost_{args.version}_{now}"

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
