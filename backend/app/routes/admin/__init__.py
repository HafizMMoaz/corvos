"""
Super admin dashboard routes.

Aggregates one sub-router per admin dashboard area (RBAC/audit log, the
settings vault, the LLM provider/model catalog, the connector credentials
vault, and now plans/feature-flags/billing; user management lands here in a
later phase). Mounted under /admin by the top-level router in `app.routes`,
which itself is mounted at /api/v1 -- so every route here is reachable at
/api/v1/admin/....
"""

from fastapi import APIRouter

from .admin_billing_routes import router as admin_billing_router
from .admin_connector_credentials_routes import (
    router as admin_connector_credentials_router,
)
from .admin_llm_routes import router as admin_llm_router
from .admin_rbac_routes import router as admin_rbac_router
from .admin_settings_routes import router as admin_settings_router

router = APIRouter(prefix="/admin", tags=["admin"])

router.include_router(admin_rbac_router)
router.include_router(admin_settings_router)
router.include_router(admin_llm_router)
router.include_router(admin_connector_credentials_router)
router.include_router(admin_billing_router)
