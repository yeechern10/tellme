from fastapi import APIRouter

from .events import router as events_router

api_router = APIRouter()
api_router.include_router(events_router, prefix="/v1", tags=["Events"])