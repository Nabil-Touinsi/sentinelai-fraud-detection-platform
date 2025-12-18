import sys
import asyncio

# ✅ Fix Windows + psycopg async: éviter ProactorEventLoop
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.transaction import Transaction
from app.services.scoring_service import ScoringService


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
