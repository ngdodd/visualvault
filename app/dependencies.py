"""
FastAPI Dependencies

This module demonstrates:
- Dependency Injection pattern in FastAPI
- Reusable dependencies across endpoints
- Type-annotated dependencies with Annotated
- Dependency composition

Dependencies in FastAPI are functions that:
1. Run before your endpoint handler
2. Can have their own dependencies (composable)
3. Can yield values (for cleanup after request)
4. Are automatically resolved by FastAPI
"""

from typing import Annotated

from fastapi import Depends, Query

from app.config import Settings, get_settings
from app.database import DbSessionDep, get_db
from app.schemas.common import PaginationParams

# Re-export database session dependency
__all__ = [
    "SettingsDep",
    "PaginationDep",
    "DbSessionDep",
    "get_db",
]


# Type alias for injected settings
# Usage: settings: SettingsDep
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_pagination(
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=100, description="Items per page")
    ] = 20,
) -> PaginationParams:
    """
    Dependency for pagination query parameters.

    Usage:
        @router.get("/items")
        async def list_items(pagination: PaginationDep):
            offset = pagination.offset
            limit = pagination.page_size
    """
    return PaginationParams(page=page, page_size=page_size)


# Type alias for pagination dependency
PaginationDep = Annotated[PaginationParams, Depends(get_pagination)]


# Note: CurrentUserDep and ApiKeyDep are defined in app/api/v1/auth.py
# to avoid circular imports. Import them from there when needed:
#
# from app.api.v1.auth import CurrentUserDep, CurrentUserOptionalDep
