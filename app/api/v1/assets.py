"""
Asset Upload and Management Endpoints

This module demonstrates:
- File upload handling with FastAPI
- File validation (type, size)
- Storage service integration
- Pagination for list endpoints
"""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, Response
from sqlalchemy import func, select

from app.api.v1.auth import CurrentUserDep
from app.config import get_settings
from app.database import DbSessionDep
from app.models.asset import Asset, AssetStatus
from app.schemas.asset import (
    AssetDetail,
    AssetList,
    AssetResponse,
    AssetUploadResponse,
)
from app.services.storage import get_storage_service
from app.utils.image import get_image_dimensions, validate_image_integrity, color_segment_image
from app.workers.tasks.processing import process_asset

router = APIRouter()


# =============================================================================
# Helper Functions
# =============================================================================


def build_asset_url(asset: Asset, request_base_url: str = "") -> str:
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


def asset_to_detail(asset: Asset) -> AssetDetail:
    """Convert an Asset model to a detailed response schema."""
    # Parse JSON fields
    ml_labels = None
    ml_colors = None

    if asset.ml_labels:
        try:
            ml_labels = json.loads(asset.ml_labels)
        except json.JSONDecodeError:
            pass

    if asset.ml_colors:
        try:
            ml_colors = json.loads(asset.ml_colors)
        except json.JSONDecodeError:
            pass

    return AssetDetail(
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
        ml_labels=ml_labels,
        ml_colors=ml_colors,
        ml_text=asset.ml_text,
        error_message=asset.error_message,
    )


# =============================================================================
# Upload Endpoints
# =============================================================================


@router.post(
    "/upload",
    response_model=AssetUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload an image",
    description="Upload a single image file. Supported formats: JPEG, PNG, GIF, WebP, BMP, TIFF.",
)
async def upload_image(
    user: CurrentUserDep,
    db: DbSessionDep,
    file: UploadFile = File(..., description="Image file to upload"),
) -> AssetUploadResponse:
    """
    Upload an image file.

    The image will be stored and queued for ML processing.
    Processing status can be checked via the asset detail endpoint.
    """
    settings = get_settings()
    storage = get_storage_service()

    # Validate content type
    if not file.content_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not determine file type",
        )

    # Check allowed types
    is_valid, error_msg = storage.validate_image(file.content_type, 0)  # Size check below
    if not is_valid and "type" in error_msg.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )

    # Read file content to get size and validate
    content = await file.read()
    file_size = len(content)

    # Check file size
    if file_size > settings.storage.max_file_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size ({file_size / 1024 / 1024:.1f}MB) exceeds maximum allowed ({settings.storage.max_file_size_mb}MB)",
        )

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file",
        )

    # Create a file-like object from content
    import io
    file_obj = io.BytesIO(content)

    # Validate image integrity
    is_valid, error_msg = validate_image_integrity(file_obj)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )

    # Get image dimensions
    dimensions = get_image_dimensions(file_obj)
    width, height = dimensions if dimensions else (None, None)

    # Reset file position for storage
    file_obj.seek(0)

    # Save to storage
    storage_path = await storage.save_file(
        file=file_obj,
        filename=file.filename or "unnamed",
        content_type=file.content_type,
        user_id=user.id,
    )

    # Create database record
    asset = Asset(
        user_id=user.id,
        filename=storage_path.split("/")[-1],  # Just the filename part
        original_filename=file.filename or "unnamed",
        content_type=file.content_type,
        file_size=file_size,
        storage_path=storage_path,
        width=width,
        height=height,
        status=AssetStatus.PENDING.value,
    )

    db.add(asset)
    await db.flush()  # Get the ID

    # Queue ML processing task
    process_asset.delay(asset.id)

    return AssetUploadResponse(
        id=asset.id,
        filename=asset.filename,
        original_filename=asset.original_filename,
        content_type=asset.content_type,
        file_size=asset.file_size,
        status=asset.status,
        message="File uploaded successfully. Processing will begin shortly.",
    )


# =============================================================================
# List and Retrieve Endpoints
# =============================================================================


@router.get(
    "",
    response_model=AssetList,
    summary="List assets",
    description="List all assets for the current user with pagination.",
)
async def list_assets(
    user: CurrentUserDep,
    db: DbSessionDep,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: AssetStatus | None = Query(None, alias="status", description="Filter by status"),
) -> AssetList:
    """
    List assets with pagination.

    - **page**: Page number (starts at 1)
    - **page_size**: Items per page (max 100)
    - **status**: Optional filter by processing status
    """
    # Build base query
    query = select(Asset).where(Asset.user_id == user.id)

    # Apply status filter
    if status_filter:
        query = query.where(Asset.status == status_filter.value)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.order_by(Asset.created_at.desc()).offset(offset).limit(page_size)

    # Execute query
    result = await db.execute(query)
    assets = result.scalars().all()

    # Calculate total pages
    pages = (total + page_size - 1) // page_size if total > 0 else 1

    return AssetList(
        items=[asset_to_response(asset) for asset in assets],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get(
    "/{asset_id}",
    response_model=AssetDetail,
    summary="Get asset details",
    description="Get detailed information about a specific asset including ML-extracted data.",
)
async def get_asset(
    asset_id: int,
    user: CurrentUserDep,
    db: DbSessionDep,
) -> AssetDetail:
    """Get details of a specific asset."""
    asset = await db.get(Asset, asset_id)

    if not asset or asset.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )

    return asset_to_detail(asset)


@router.get(
    "/{asset_id}/file",
    summary="Download asset file",
    description="Download the original uploaded file.",
    responses={
        200: {
            "content": {"image/*": {}},
            "description": "The image file",
        },
        404: {"description": "Asset not found"},
    },
)
async def download_asset(
    asset_id: int,
    user: CurrentUserDep,
    db: DbSessionDep,
) -> FileResponse:
    """Download the original uploaded file."""
    asset = await db.get(Asset, asset_id)

    if not asset or asset.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )

    storage = get_storage_service()
    file_path = await storage.get_file_path(asset.storage_path)

    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found in storage",
        )

    return FileResponse(
        path=file_path,
        media_type=asset.content_type,
        filename=asset.original_filename,
    )


# =============================================================================
# Delete Endpoint
# =============================================================================


@router.delete(
    "/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete asset",
    description="Delete an asset and its associated file.",
)
async def delete_asset(
    asset_id: int,
    user: CurrentUserDep,
    db: DbSessionDep,
) -> None:
    """Delete an asset and its file from storage."""
    asset = await db.get(Asset, asset_id)

    if not asset or asset.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )

    # Delete file from storage
    storage = get_storage_service()
    await storage.delete_file(asset.storage_path)

    # Delete database record
    await db.delete(asset)


# =============================================================================
# Batch Operations
# =============================================================================


@router.post(
    "/upload/batch",
    response_model=list[AssetUploadResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Upload multiple images",
    description="Upload multiple image files at once. Maximum 10 files per request.",
)
async def upload_images_batch(
    user: CurrentUserDep,
    db: DbSessionDep,
    files: list[UploadFile] = File(..., description="Image files to upload"),
) -> list[AssetUploadResponse]:
    """
    Upload multiple images at once.

    Maximum 10 files per request.
    Each file is validated independently.
    """
    if len(files) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 10 files per batch upload",
        )

    results = []
    errors = []

    for i, file in enumerate(files):
        try:
            # Reuse single upload logic (simplified here)
            result = await upload_image(user, db, file)
            results.append(result)
        except HTTPException as e:
            errors.append({
                "index": i,
                "filename": file.filename,
                "error": e.detail,
            })

    if errors and not results:
        # All failed
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "All uploads failed", "errors": errors},
        )

    # Return successful uploads (partial success is OK)
    return results


# =============================================================================
# Image Analysis Endpoints
# =============================================================================


@router.get(
    "/{asset_id}/segment",
    summary="Color segmentation",
    description="Get a color-segmented version of the image using k-means clustering.",
    responses={
        200: {
            "content": {"image/png": {}},
            "description": "Segmented image",
        },
        404: {"description": "Asset not found"},
    },
)
async def segment_asset(
    asset_id: int,
    user: CurrentUserDep,
    db: DbSessionDep,
    num_clusters: int = Query(5, ge=2, le=16, description="Number of color clusters"),
    format: str = Query("png", regex="^(png|jpeg)$", description="Output format"),
) -> Response:
    """
    Generate a color-segmented version of an image.

    Uses k-means clustering to reduce the image to a specified number of colors.
    This creates a posterized/simplified version of the image.

    - **num_clusters**: Number of distinct colors in output (2-16)
    - **format**: Output image format (png or jpeg)
    """
    asset = await db.get(Asset, asset_id)

    if not asset or asset.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )

    storage = get_storage_service()
    file_path = await storage.get_file_path(asset.storage_path)

    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found in storage",
        )

    # Generate segmented image
    with open(file_path, "rb") as f:
        output_format = format.upper()
        segmented_bytes, cluster_colors = color_segment_image(
            f, num_clusters=num_clusters, output_format=output_format
        )

    media_type = "image/png" if output_format == "PNG" else "image/jpeg"

    return Response(
        content=segmented_bytes,
        media_type=media_type,
        headers={
            "X-Cluster-Colors": json.dumps(cluster_colors),
        },
    )


@router.get(
    "/{asset_id}/segment/info",
    summary="Color segmentation info",
    description="Get color cluster information without generating the image.",
)
async def segment_asset_info(
    asset_id: int,
    user: CurrentUserDep,
    db: DbSessionDep,
    num_clusters: int = Query(5, ge=2, le=16, description="Number of color clusters"),
) -> dict:
    """
    Get color cluster information for an image.

    Returns the cluster colors and their percentages without
    generating the full segmented image.
    """
    asset = await db.get(Asset, asset_id)

    if not asset or asset.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )

    storage = get_storage_service()
    file_path = await storage.get_file_path(asset.storage_path)

    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found in storage",
        )

    # Generate segmentation info
    with open(file_path, "rb") as f:
        _, cluster_colors = color_segment_image(f, num_clusters=num_clusters)

    return {
        "asset_id": asset_id,
        "num_clusters": num_clusters,
        "clusters": cluster_colors,
    }
