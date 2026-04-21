"""
Tag Management Endpoints

This module provides endpoints for:
- Managing user's custom tags
- Adding/removing tags from assets
- Getting all tags for zero-shot classification
"""

import json
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func

from app.api.v1.auth import CurrentUserDep
from app.database import DbSessionDep
from app.models.asset import Asset
from app.models.tag import UserTag

router = APIRouter()


# =============================================================================
# Schemas
# =============================================================================


class TagCreate(BaseModel):
    """Request to create or add a tag."""
    name: str = Field(..., min_length=1, max_length=100, description="Tag name")


class TagResponse(BaseModel):
    """Response for a single tag."""
    id: int
    name: str
    usage_count: int


class AssetTagsUpdate(BaseModel):
    """Request to update tags on an asset."""
    tags: list[str] = Field(..., description="List of tag names to set on the asset")


class AssetTagsResponse(BaseModel):
    """Response with asset's tags."""
    asset_id: int
    custom_tags: list[str]
    ml_labels: list[str]


# =============================================================================
# User Tag Endpoints
# =============================================================================


@router.get(
    "",
    response_model=list[TagResponse],
    summary="List user tags",
    description="Get all custom tags created by the user.",
)
async def list_tags(
    user: CurrentUserDep,
    db: DbSessionDep,
    sort_by: str = Query("usage", regex="^(usage|name|recent)$", description="Sort order"),
) -> list[TagResponse]:
    """
    List all tags created by the user.

    These tags are used for:
    1. Manual image tagging
    2. Zero-shot classification categories
    """
    query = select(UserTag).where(UserTag.user_id == user.id)

    if sort_by == "usage":
        query = query.order_by(UserTag.usage_count.desc())
    elif sort_by == "name":
        query = query.order_by(UserTag.name)
    else:  # recent
        query = query.order_by(UserTag.updated_at.desc())

    result = await db.execute(query)
    tags = result.scalars().all()

    return [
        TagResponse(id=tag.id, name=tag.name, usage_count=tag.usage_count)
        for tag in tags
    ]


@router.post(
    "",
    response_model=TagResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a tag",
    description="Create a new custom tag.",
)
async def create_tag(
    data: TagCreate,
    user: CurrentUserDep,
    db: DbSessionDep,
) -> TagResponse:
    """
    Create a new custom tag.

    The tag will be added to zero-shot classification for future images.
    """
    # Normalize tag name
    tag_name = data.name.strip().lower()

    # Check if tag already exists
    result = await db.execute(
        select(UserTag)
        .where(UserTag.user_id == user.id)
        .where(UserTag.name == tag_name)
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tag '{tag_name}' already exists",
        )

    # Create new tag
    tag = UserTag(user_id=user.id, name=tag_name, usage_count=0)
    db.add(tag)
    await db.flush()

    return TagResponse(id=tag.id, name=tag.name, usage_count=tag.usage_count)


@router.delete(
    "/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a tag",
    description="Delete a custom tag.",
)
async def delete_tag(
    tag_id: int,
    user: CurrentUserDep,
    db: DbSessionDep,
) -> None:
    """Delete a custom tag."""
    tag = await db.get(UserTag, tag_id)

    if not tag or tag.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found",
        )

    await db.delete(tag)


# =============================================================================
# Asset Tag Endpoints
# =============================================================================


@router.get(
    "/assets/{asset_id}",
    response_model=AssetTagsResponse,
    summary="Get asset tags",
    description="Get all tags (custom and ML-generated) for an asset.",
)
async def get_asset_tags(
    asset_id: int,
    user: CurrentUserDep,
    db: DbSessionDep,
) -> AssetTagsResponse:
    """Get all tags for an asset."""
    asset = await db.get(Asset, asset_id)

    if not asset or asset.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )

    custom_tags = []
    if asset.custom_tags:
        try:
            custom_tags = json.loads(asset.custom_tags)
        except json.JSONDecodeError:
            pass

    ml_labels = []
    if asset.ml_labels:
        try:
            ml_labels = json.loads(asset.ml_labels)
        except json.JSONDecodeError:
            pass

    return AssetTagsResponse(
        asset_id=asset.id,
        custom_tags=custom_tags,
        ml_labels=ml_labels,
    )


@router.put(
    "/assets/{asset_id}",
    response_model=AssetTagsResponse,
    summary="Update asset tags",
    description="Set custom tags on an asset.",
)
async def update_asset_tags(
    asset_id: int,
    data: AssetTagsUpdate,
    user: CurrentUserDep,
    db: DbSessionDep,
) -> AssetTagsResponse:
    """
    Update custom tags on an asset.

    This will:
    1. Set the custom_tags on the asset
    2. Create any new tags in the user's tag library
    3. Update usage counts for all tags
    """
    asset = await db.get(Asset, asset_id)

    if not asset or asset.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )

    # Get existing custom tags
    old_tags = set()
    if asset.custom_tags:
        try:
            old_tags = set(json.loads(asset.custom_tags))
        except json.JSONDecodeError:
            pass

    # Normalize new tags
    new_tags = set(tag.strip().lower() for tag in data.tags if tag.strip())

    # Update asset's custom_tags
    asset.custom_tags = json.dumps(sorted(new_tags))

    # Update user's tag library
    for tag_name in new_tags:
        # Check if tag exists
        result = await db.execute(
            select(UserTag)
            .where(UserTag.user_id == user.id)
            .where(UserTag.name == tag_name)
        )
        user_tag = result.scalar_one_or_none()

        if user_tag:
            # Increment usage count if this is a new tag for this asset
            if tag_name not in old_tags:
                user_tag.usage_count += 1
        else:
            # Create new tag
            user_tag = UserTag(user_id=user.id, name=tag_name, usage_count=1)
            db.add(user_tag)

    # Decrement usage counts for removed tags
    removed_tags = old_tags - new_tags
    for tag_name in removed_tags:
        result = await db.execute(
            select(UserTag)
            .where(UserTag.user_id == user.id)
            .where(UserTag.name == tag_name)
        )
        user_tag = result.scalar_one_or_none()
        if user_tag and user_tag.usage_count > 0:
            user_tag.usage_count -= 1

    await db.flush()

    # Get ML labels for response
    ml_labels = []
    if asset.ml_labels:
        try:
            ml_labels = json.loads(asset.ml_labels)
        except json.JSONDecodeError:
            pass

    return AssetTagsResponse(
        asset_id=asset.id,
        custom_tags=sorted(new_tags),
        ml_labels=ml_labels,
    )


@router.post(
    "/assets/{asset_id}/add",
    response_model=AssetTagsResponse,
    summary="Add tag to asset",
    description="Add a single tag to an asset.",
)
async def add_tag_to_asset(
    asset_id: int,
    data: TagCreate,
    user: CurrentUserDep,
    db: DbSessionDep,
) -> AssetTagsResponse:
    """Add a single tag to an asset."""
    asset = await db.get(Asset, asset_id)

    if not asset or asset.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )

    # Get existing tags
    current_tags = set()
    if asset.custom_tags:
        try:
            current_tags = set(json.loads(asset.custom_tags))
        except json.JSONDecodeError:
            pass

    # Normalize and add new tag
    tag_name = data.name.strip().lower()
    if tag_name in current_tags:
        # Tag already exists on asset
        ml_labels = []
        if asset.ml_labels:
            try:
                ml_labels = json.loads(asset.ml_labels)
            except json.JSONDecodeError:
                pass
        return AssetTagsResponse(
            asset_id=asset.id,
            custom_tags=sorted(current_tags),
            ml_labels=ml_labels,
        )

    current_tags.add(tag_name)
    asset.custom_tags = json.dumps(sorted(current_tags))

    # Update user's tag library
    result = await db.execute(
        select(UserTag)
        .where(UserTag.user_id == user.id)
        .where(UserTag.name == tag_name)
    )
    user_tag = result.scalar_one_or_none()

    if user_tag:
        user_tag.usage_count += 1
    else:
        user_tag = UserTag(user_id=user.id, name=tag_name, usage_count=1)
        db.add(user_tag)

    await db.flush()

    ml_labels = []
    if asset.ml_labels:
        try:
            ml_labels = json.loads(asset.ml_labels)
        except json.JSONDecodeError:
            pass

    return AssetTagsResponse(
        asset_id=asset.id,
        custom_tags=sorted(current_tags),
        ml_labels=ml_labels,
    )


@router.delete(
    "/assets/{asset_id}/remove/{tag_name}",
    response_model=AssetTagsResponse,
    summary="Remove tag from asset",
    description="Remove a tag from an asset.",
)
async def remove_tag_from_asset(
    asset_id: int,
    tag_name: str,
    user: CurrentUserDep,
    db: DbSessionDep,
) -> AssetTagsResponse:
    """Remove a tag from an asset."""
    asset = await db.get(Asset, asset_id)

    if not asset or asset.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )

    # Get existing tags
    current_tags = set()
    if asset.custom_tags:
        try:
            current_tags = set(json.loads(asset.custom_tags))
        except json.JSONDecodeError:
            pass

    # Normalize and remove tag
    tag_name = tag_name.strip().lower()
    if tag_name not in current_tags:
        ml_labels = []
        if asset.ml_labels:
            try:
                ml_labels = json.loads(asset.ml_labels)
            except json.JSONDecodeError:
                pass
        return AssetTagsResponse(
            asset_id=asset.id,
            custom_tags=sorted(current_tags),
            ml_labels=ml_labels,
        )

    current_tags.discard(tag_name)
    asset.custom_tags = json.dumps(sorted(current_tags)) if current_tags else None

    # Decrement usage count
    result = await db.execute(
        select(UserTag)
        .where(UserTag.user_id == user.id)
        .where(UserTag.name == tag_name)
    )
    user_tag = result.scalar_one_or_none()
    if user_tag and user_tag.usage_count > 0:
        user_tag.usage_count -= 1

    await db.flush()

    ml_labels = []
    if asset.ml_labels:
        try:
            ml_labels = json.loads(asset.ml_labels)
        except json.JSONDecodeError:
            pass

    return AssetTagsResponse(
        asset_id=asset.id,
        custom_tags=sorted(current_tags),
        ml_labels=ml_labels,
    )
