"""Admin API package: one aggregating router mounted at /api/admin.

Every sub-router gates on a permission via require_permission(...); the shared
`router` is imported by main.py.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.admin import audit, flags, me, overview, roles, users
from app.api.admin import monitoring

router = APIRouter(prefix="/admin", tags=["admin"])
router.include_router(me.router)
router.include_router(overview.router)
router.include_router(users.router)
router.include_router(roles.router)
router.include_router(flags.router)
router.include_router(audit.router)
router.include_router(monitoring.router)
