from fastapi import APIRouter
from app.api import health, cases

api_router = APIRouter(prefix="/api/v1")

# Mount system and domain routers
api_router.include_router(health.router)
api_router.include_router(cases.router)
