"""
Similarity Search Endpoints

This module provides semantic search capabilities:
- Text-to-image search (find images matching a description)
- Image-to-image search (find similar images)
- Combined filtering with metadata

Uses CLIP embeddings for semantic understanding.
"""

import json
from typing import Annotated

import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select

from app.api.v1.auth import CurrentUserDep
from app.config import get_settings
from app.database import DbSessionDep
from app.ml.clip_service import get_clip_service
from app.models.asset import Asset, AssetStatus
from app.schemas.asset import AssetResponse
from app.utils.image import get_image_dimensions, validate_image_integrity
from pydantic import BaseModel, Field
from PIL import Image
import io

router = APIRouter()


# =============================================================================
# Schemas
# =============================================================================


class SearchResult(BaseModel):
    """Single search result with similarity score."""
    asset: AssetResponse
    similarity: float = Field(..., ge=-1.0, le=1.0, description="Cosine similarity score")


class SearchResults(BaseModel):
    """List of search results."""
    results: list[SearchResult]
    query_type: str  # "text" or "image"
    total_searched: int


class TextSearchRequest(BaseModel):
    """Request body for text search."""
    query: str = Field(..., min_length=1, max_length=500, description="Search query")
    limit: int = Field(20, ge=1, le=100, description="Maximum results to return")
    min_similarity: float = Field(0.1, ge=0.0, le=1.0, description="Minimum similarity threshold")


# =============================================================================
# Helper Functions
# =============================================================================


def build_asset_url(asset: Asset) -> str:
    """Build the URL to access an asset."""
    settings = get_settings()
    return f"{settings.api_v1_prefix}/assets/{asset.id}/file"


def asset_to_response(asset: Asset) -> AssetResponse:
    """Convert an Asset model to a response schema."""
    return AssetResponse(
        id=asset.id,
        filename=asset.filename,
        original_filename=asset.original_filename,
        content_type=asset.content_type,
        file_size=asset.file_size,
        width=asset.width,
        height=asset.height,
        status=asset.status,
        created_at=asset.created_at,
        processed_at=asset.processed_at,
        url=build_asset_url(asset),
    )


async def get_user_embeddings(db, user_id: int) -> list[tuple[Asset, np.ndarray]]:
    """
    Load all embeddings for a user's processed assets.

    Returns list of (asset, embedding) tuples.
    """
    result = await db.execute(
        select(Asset)
        .where(Asset.user_id == user_id)
        .where(Asset.status == AssetStatus.COMPLETED.value)
        .where(Asset.embedding_vector.isnot(None))
    )
    assets = result.scalars().all()

    embeddings = []
    for asset in assets:
        try:
            vector = np.array(json.loads(asset.embedding_vector))
            embeddings.append((asset, vector))
        except (json.JSONDecodeError, TypeError):
            continue

    return embeddings


# =============================================================================
# Search Endpoints
# =============================================================================


@router.post(
    "/text",
    response_model=SearchResults,
    summary="Search by text",
    description="Find images that match a text description using semantic search.",
)
async def search_by_text(
    request: TextSearchRequest,
    user: CurrentUserDep,
    db: DbSessionDep,
) -> SearchResults:
    """
    Search images using natural language.

    Example queries:
    - "a photo of a dog on the beach"
    - "sunset over mountains"
    - "people at a restaurant"

    The search uses CLIP to find semantically similar images.
    """
    # Get CLIP service
    clip_service = get_clip_service()

    # Generate text embedding
    query_embedding = clip_service.get_text_embedding(request.query)

    # Get user's embeddings
    asset_embeddings = await get_user_embeddings(db, user.id)

    if not asset_embeddings:
        return SearchResults(
            results=[],
            query_type="text",
            total_searched=0,
        )

    # Compute similarities
    results = []
    for asset, embedding in asset_embeddings:
        similarity = float(np.dot(query_embedding, embedding))
        if similarity >= request.min_similarity:
            results.append((asset, similarity))

    # Sort by similarity (descending)
    results.sort(key=lambda x: x[1], reverse=True)

    # Limit results
    results = results[:request.limit]

    return SearchResults(
        results=[
            SearchResult(
                asset=asset_to_response(asset),
                similarity=round(similarity, 4),
            )
            for asset, similarity in results
        ],
        query_type="text",
        total_searched=len(asset_embeddings),
    )


@router.post(
    "/similar/{asset_id}",
    response_model=SearchResults,
    summary="Find similar images",
    description="Find images similar to a specific asset.",
)
async def search_similar(
    asset_id: int,
    user: CurrentUserDep,
    db: DbSessionDep,
    limit: int = Query(20, ge=1, le=100),
    min_similarity: float = Query(0.5, ge=0.0, le=1.0),
) -> SearchResults:
    """
    Find images similar to a given asset.

    The query asset must be owned by the user and fully processed.
    """
    # Get the query asset
    query_asset = await db.get(Asset, asset_id)
    if not query_asset or query_asset.user_id != user.id:
        raise HTTPException(status_code=404, detail="Asset not found")

    if query_asset.status != AssetStatus.COMPLETED.value:
        raise HTTPException(
            status_code=400,
            detail="Asset must be fully processed to search for similar images",
        )

    if not query_asset.embedding_vector:
        raise HTTPException(
            status_code=400,
            detail="Asset does not have an embedding",
        )

    # Parse query embedding
    try:
        query_embedding = np.array(json.loads(query_asset.embedding_vector))
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(
            status_code=500,
            detail="Invalid embedding data",
        )

    # Get all other embeddings
    asset_embeddings = await get_user_embeddings(db, user.id)

    # Compute similarities (excluding the query asset)
    results = []
    for asset, embedding in asset_embeddings:
        if asset.id == asset_id:
            continue
        similarity = float(np.dot(query_embedding, embedding))
        if similarity >= min_similarity:
            results.append((asset, similarity))

    # Sort by similarity
    results.sort(key=lambda x: x[1], reverse=True)
    results = results[:limit]

    return SearchResults(
        results=[
            SearchResult(
                asset=asset_to_response(asset),
                similarity=round(similarity, 4),
            )
            for asset, similarity in results
        ],
        query_type="image",
        total_searched=len(asset_embeddings) - 1,  # Exclude query asset
    )


@router.post(
    "/image",
    response_model=SearchResults,
    summary="Search by image upload",
    description="Upload an image to find similar images in your collection.",
)
async def search_by_image(
    user: CurrentUserDep,
    db: DbSessionDep,
    file: UploadFile = File(..., description="Image to search with"),
    limit: int = Query(20, ge=1, le=100),
    min_similarity: float = Query(0.5, ge=0.0, le=1.0),
) -> SearchResults:
    """
    Search using an uploaded image.

    The uploaded image is processed to generate an embedding,
    then compared against all user's assets.
    """
    # Validate the uploaded image
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    content = await file.read()
    file_obj = io.BytesIO(content)

    is_valid, error = validate_image_integrity(file_obj)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error)

    # Load as PIL Image
    file_obj.seek(0)
    image = Image.open(file_obj)
    if image.mode != "RGB":
        image = image.convert("RGB")

    # Generate embedding
    clip_service = get_clip_service()
    query_embedding = clip_service.get_image_embedding(image)

    # Get user's embeddings
    asset_embeddings = await get_user_embeddings(db, user.id)

    if not asset_embeddings:
        return SearchResults(
            results=[],
            query_type="image",
            total_searched=0,
        )

    # Compute similarities
    results = []
    for asset, embedding in asset_embeddings:
        similarity = float(np.dot(query_embedding, embedding))
        if similarity >= min_similarity:
            results.append((asset, similarity))

    # Sort and limit
    results.sort(key=lambda x: x[1], reverse=True)
    results = results[:limit]

    return SearchResults(
        results=[
            SearchResult(
                asset=asset_to_response(asset),
                similarity=round(similarity, 4),
            )
            for asset, similarity in results
        ],
        query_type="image",
        total_searched=len(asset_embeddings),
    )


@router.get(
    "/labels/available",
    summary="Get available labels",
    description="Get all unique labels across the user's processed images.",
)
async def get_available_labels(
    user: CurrentUserDep,
    db: DbSessionDep,
) -> list[str]:
    """
    Get all unique labels from the user's processed assets.

    Returns a sorted list of unique labels.
    """
    result = await db.execute(
        select(Asset)
        .where(Asset.user_id == user.id)
        .where(Asset.status == AssetStatus.COMPLETED.value)
        .where(Asset.ml_labels.isnot(None))
    )
    assets = result.scalars().all()

    all_labels = set()
    for asset in assets:
        try:
            labels = json.loads(asset.ml_labels)
            all_labels.update(labels)
        except (json.JSONDecodeError, TypeError):
            continue

    return sorted(all_labels)


@router.get(
    "/labels",
    summary="Search by label",
    description="Find images with specific ML-detected labels.",
)
async def search_by_label(
    user: CurrentUserDep,
    db: DbSessionDep,
    label: str = Query(..., min_length=1, description="Label to search for"),
    limit: int = Query(50, ge=1, le=100),
) -> list[AssetResponse]:
    """
    Search images by ML-generated labels.

    Labels are generated during processing using zero-shot classification.
    """
    # Get processed assets
    result = await db.execute(
        select(Asset)
        .where(Asset.user_id == user.id)
        .where(Asset.status == AssetStatus.COMPLETED.value)
        .where(Asset.ml_labels.isnot(None))
    )
    assets = result.scalars().all()

    # Filter by label
    matching = []
    label_lower = label.lower()
    for asset in assets:
        try:
            labels = json.loads(asset.ml_labels)
            if any(label_lower in l.lower() for l in labels):
                matching.append(asset)
        except (json.JSONDecodeError, TypeError):
            continue

    # Limit results
    matching = matching[:limit]

    return [asset_to_response(asset) for asset in matching]
