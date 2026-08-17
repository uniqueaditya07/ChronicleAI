from fastapi import APIRouter
from app.api.health import router as health_router
from app.api.cases import router as cases_router
from app.api.sources import router as sources_router

api_router = APIRouter(prefix="/api/v1")

# Mount system and domain routers
api_router.include_router(health_router)
api_router.include_router(cases_router)
api_router.include_router(sources_router)
