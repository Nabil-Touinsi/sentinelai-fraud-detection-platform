from __future__ import annotations

from fastapi import Depends, Request

from app.core.security import require_api_key

"""
Dépendances API.

Rôle (fonctionnel) :
- Centralise les dépendances réutilisables sur les routes.
- Ici : protection “démo” via clé API (header).
"""


async def require_demo_auth(request: Request) -> None:
    # Auth démo basée sur une API key
    await require_api_key(request)


# Dépendance prête à l’emploi pour protéger un endpoint
DemoAuthDep = Depends(require_demo_auth)
