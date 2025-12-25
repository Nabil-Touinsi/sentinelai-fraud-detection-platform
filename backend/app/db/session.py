from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.settings import settings

"""
DB Session.

Rôle (fonctionnel) :
- Initialise l’engine SQLAlchemy en mode async (runtime FastAPI).
- Fournit une factory de sessions AsyncSession (AsyncSessionLocal).
- Expose `get_db()` comme dépendance FastAPI pour injecter une session DB
  dans les endpoints/services (Depends(get_db)).

Notes :
- expire_on_commit=False : permet de réutiliser les objets après commit sans rechargement automatique.
- echo=False : désactive le log SQL brut (on préfère les logs applicatifs en JSON).
"""

# Engine async utilisé par l’application (SQLAlchemy async)
engine = create_async_engine(settings.DATABASE_URL, echo=False)

# Factory de sessions async
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db():
    """Dépendance FastAPI : yield une session DB et garantit sa fermeture."""
    async with AsyncSessionLocal() as session:
        yield session
