"""
app.db

Package base de données : connexion, session et helpers d’accès DB.

Contenu typique :
- session : création et fourniture des sessions SQLAlchemy (async) pour FastAPI (Depends(get_db)).
- migrations : configuration Alembic (côté sync) via DATABASE_URL_SYNC.
"""
