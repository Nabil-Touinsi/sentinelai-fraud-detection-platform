import sys
import asyncio

# Windows: compat event loop (évite certains soucis avec drivers async PostgreSQL)
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.transaction import Transaction
from app.services.scoring_service import ScoringService

"""
Script CLI: score_one

Rôle (fonctionnel) :
- Récupère la transaction la plus récente en base.
- Exécute le scoring via ScoringService (règles + ML optionnel).
- Persiste le score (risk_scores) et affiche un résumé (score, risk_level, factors).

Usage typique :
- Debug local / vérification rapide du scoring sans passer par l’API.
- Validation que DB + modèles + pipeline scoring fonctionnent de bout en bout.

Notes :
- Le fix Windows ajuste la policy asyncio pour éviter des incompatibilités
  connues avec certains drivers PostgreSQL async.
- Ce script ne crée pas de transaction : il score la dernière existante.
"""


async def main():
    async with AsyncSessionLocal() as db:
        tx = (
            (await db.execute(select(Transaction).order_by(Transaction.occurred_at.desc())))
            .scalars()
            .first()
        )

        if not tx:
            print("Aucune transaction en base.")
            return

        svc = ScoringService()
        res = await svc.score_and_persist(db, tx)

        print("TX:", tx.id)
        print("Score:", res.score, res.risk_level)
        print("Factors:", res.factors)


if __name__ == "__main__":
    asyncio.run(main())
