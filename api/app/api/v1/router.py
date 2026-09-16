from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    device,
    health,
    heartbeats,
    sessions,
    stats,
    users,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(heartbeats.router, prefix="/heartbeats", tags=["heartbeats"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(device.router, prefix="/devices", tags=["devices"])
api_router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
api_router.include_router(stats.router, prefix="/stats", tags=["stats"])
