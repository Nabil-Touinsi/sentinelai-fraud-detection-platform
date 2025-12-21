from __future__ import annotations

from fastapi import Depends, Request

from app.core.security import require_api_key


async def require_demo_auth(request: Request) -> None:
    await require_api_key(request)


DemoAuthDep = Depends(require_demo_auth)
