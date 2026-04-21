"""
API v1 Router - Central routing configuration

This module demonstrates:
- Router organization and inclusion
- API versioning strategy
- Centralized route management
"""

from fastapi import APIRouter

from app.api.v1 import analysis, assets, auth, health, search, tags

# Create the main API router for v1
api_router = APIRouter()

# Include sub-routers with their prefixes and tags
api_router.include_router(
    health.router,
    prefix="/health",
    tags=["Health"],
)

api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"],
)

api_router.include_router(
    assets.router,
    prefix="/assets",
    tags=["Assets"],
)

api_router.include_router(
    search.router,
    prefix="/search",
    tags=["Search"],
)

api_router.include_router(
    analysis.router,
    prefix="/analysis",
    tags=["Analysis & MLOps"],
)

api_router.include_router(
    tags.router,
    prefix="/tags",
    tags=["Tags"],
)

# Future routers will be added here:
# api_router.include_router(feedback.router, prefix="/feedback", tags=["Feedback"])
