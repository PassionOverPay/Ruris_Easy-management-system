from fastapi import APIRouter

from app.api.routes import accounting, auth, health, purchasing, warehouse

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(purchasing.router, prefix="/purchasing", tags=["purchasing"])
api_router.include_router(warehouse.router, prefix="/warehouse", tags=["warehouse"])
api_router.include_router(accounting.router, prefix="/accounting", tags=["accounting"])
