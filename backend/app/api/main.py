from fastapi import APIRouter

from app.api.routes import accounting, admin, health, purchasing, warehouse

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(purchasing.router, prefix="/purchasing", tags=["purchasing"])
api_router.include_router(warehouse.router, prefix="/warehouse", tags=["warehouse"])
api_router.include_router(accounting.router, prefix="/accounting", tags=["accounting"])
