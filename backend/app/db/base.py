from sqlalchemy.orm import DeclarativeBase

"""
DB Base.

Rôle (fonctionnel) :
- Définit la classe Base SQLAlchemy commune à tous les modèles ORM.
- Sert de point d’ancrage pour :
  - la déclaration des tables (models/*),
  - la création de schéma (migrations / metadata),
  - l’introspection ORM.

Note :
- Tous les modèles doivent hériter de Base pour être enregistrés dans la metadata.
"""


class Base(DeclarativeBase):
    """Classe racine ORM (SQLAlchemy Declarative)."""
    pass
