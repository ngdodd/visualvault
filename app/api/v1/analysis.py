"""
Image Analysis Endpoints

This module provides ML-powered image analysis capabilities:
- Object detection (YOLO)
- Model metrics for MLOps monitoring
- Support for multiple model versions

These endpoints demonstrate MLOps concepts like model versioning,
A/B testing, and performance monitoring.
"""

import io
import json
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from PIL import Image, ImageDraw, ImageFont

from app.api.v1.auth import CurrentUserDep, CurrentUserOptionalDep
from app.database import DbSessionDep
from app.ml.yolo_service import get_yolo_service, MODEL_VARIANTS, DEFAULT_MODEL
from app.ml.style_transfer import get_style_service, PRESET_STYLES
from app.models.asset import Asset, AssetStatus
from app.services.auth import AuthService
from app.services.storage import get_storage_service

router = APIRouter()


# =============================================================================
# Object Detection Endpoints
# =============================================================================


@router.get(
    "/models",
    summary="List available models",
    description="Get information about available object detection models.",
)
async def list_models() -> dict:
    """
    List all available YOLO models with their characteristics.

    Useful for MLOps dashboards and model selection UIs.
    """
    service = get_yolo_service()
    return {
        "models": service.get_available_models(),
        "default": DEFAULT_MODEL,
    }


@router.get(
    "/detect/{asset_id}",
    summary="Detect objects in an asset",
    description="Run object detection on an uploaded image.",
)
async def detect_objects(
    asset_id: int,
    db: DbSessionDep,
    user: CurrentUserOptionalDep = None,
    token: str | None = Query(None, description="JWT token for browser requests"),
    model: str = Query(DEFAULT_MODEL, description="Model to use for detection"),
    confidence: float = Query(0.25, ge=0.0, le=1.0, description="Minimum confidence threshold"),
    max_detections: int = Query(50, ge=1, le=200, description="Maximum detections to return"),
) -> dict:
    """
    Run object detection on an image.

    Returns detected objects with bounding boxes, labels, and confidence scores.
    Also includes inference metrics for MLOps monitoring.
    """
    # Handle token-based auth
    if not user and token:
        auth_service = AuthService(db)
        user_id = auth_service.verify_access_token(token)
        if user_id:
            user = await auth_service.get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    # Get the asset
    asset = await db.get(Asset, asset_id)
    if not asset or asset.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )

    if asset.status != AssetStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Asset must be fully processed",
        )

    # Validate model
    if model not in MODEL_VARIANTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid model. Available: {list(MODEL_VARIANTS.keys())}",
        )

    # Get file path
    storage = get_storage_service()
    file_path = await storage.get_file_path(asset.storage_path)
    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found in storage",
        )

    # Run detection
    service = get_yolo_service()
    with open(file_path, "rb") as f:
        result = service.detect(
            image=f,
            model_name=model,
            confidence_threshold=confidence,
            max_detections=max_detections,
        )

    return {
        "asset_id": asset_id,
        **result.to_dict(),
    }


@router.get(
    "/detect/{asset_id}/visualize",
    summary="Visualize object detection",
    description="Get an image with detection bounding boxes drawn on it.",
    responses={
        200: {
            "content": {"image/png": {}},
            "description": "Image with bounding boxes",
        },
    },
)
async def visualize_detections(
    asset_id: int,
    db: DbSessionDep,
    user: CurrentUserOptionalDep = None,
    token: str | None = Query(None, description="JWT token for browser requests"),
    model: str = Query(DEFAULT_MODEL, description="Model to use"),
    confidence: float = Query(0.25, ge=0.0, le=1.0, description="Minimum confidence"),
    max_detections: int = Query(50, ge=1, le=200, description="Max detections"),
    show_labels: bool = Query(True, description="Show labels on boxes"),
    show_confidence: bool = Query(True, description="Show confidence scores"),
) -> Response:
    """
    Generate an image with detection bounding boxes overlaid.

    Useful for visual inspection and debugging.
    """
    # Handle token-based auth
    if not user and token:
        auth_service = AuthService(db)
        user_id = auth_service.verify_access_token(token)
        if user_id:
            user = await auth_service.get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    # Get the asset
    asset = await db.get(Asset, asset_id)
    if not asset or asset.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )

    # Validate model
    if model not in MODEL_VARIANTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid model. Available: {list(MODEL_VARIANTS.keys())}",
        )

    # Get file
    storage = get_storage_service()
    file_path = await storage.get_file_path(asset.storage_path)
    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    # Load image and run detection
    image = Image.open(file_path)
    if image.mode != "RGB":
        image = image.convert("RGB")

    service = get_yolo_service()
    result = service.detect(
        image=image,
        model_name=model,
        confidence_threshold=confidence,
        max_detections=max_detections,
    )

    # Draw bounding boxes
    draw = ImageDraw.Draw(image)

    # Color palette for different classes
    colors = [
        "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7",
        "#DDA0DD", "#98D8C8", "#F7DC6F", "#BB8FCE", "#85C1E9",
    ]

    # Try to use a reasonable font
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    except (OSError, IOError):
        font = ImageFont.load_default()

    label_colors = {}
    for detection in result.detections:
        # Get consistent color for this label
        if detection.label not in label_colors:
            label_colors[detection.label] = colors[len(label_colors) % len(colors)]
        color = label_colors[detection.label]

        x1, y1, x2, y2 = detection.bbox

        # Draw box
        draw.rectangle([x1, y1, x2, y2], outline=color, width=3)

        # Draw label
        if show_labels:
            label_text = detection.label
            if show_confidence:
                label_text += f" {detection.confidence:.0%}"

            # Get text size for background
            text_bbox = draw.textbbox((x1, y1), label_text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]

            # Draw label background
            draw.rectangle(
                [x1, y1 - text_height - 6, x1 + text_width + 8, y1],
                fill=color,
            )
            draw.text((x1 + 4, y1 - text_height - 4), label_text, fill="white", font=font)

    # Save to bytes
    output = io.BytesIO()
    image.save(output, format="PNG")
    output.seek(0)

    return Response(
        content=output.getvalue(),
        media_type="image/png",
        headers={
            "X-Model": model,
            "X-Detections": str(len(result.detections)),
            "X-Inference-Time-Ms": str(round(result.inference_time_ms, 2)),
        },
    )


# =============================================================================
# MLOps Metrics Endpoints
# =============================================================================


@router.get(
    "/metrics",
    summary="Get model metrics",
    description="Get inference metrics for MLOps monitoring.",
)
async def get_metrics(
    user: CurrentUserDep,
    model: str | None = Query(None, description="Specific model to get metrics for"),
) -> dict:
    """
    Get inference metrics across all models or for a specific model.

    Returns:
    - Total inferences
    - Average inference time
    - Average detections per image
    """
    service = get_yolo_service()
    return {
        "metrics": service.get_metrics(model),
    }


@router.post(
    "/metrics/reset",
    summary="Reset metrics",
    description="Reset inference metrics (admin only in production).",
)
async def reset_metrics(
    user: CurrentUserDep,
    model: str | None = Query(None, description="Specific model to reset"),
) -> dict:
    """Reset metrics for monitoring purposes."""
    service = get_yolo_service()
    service.reset_metrics(model)
    return {"message": "Metrics reset", "model": model or "all"}


@router.get(
    "/compare",
    summary="Compare models",
    description="Run detection with multiple models for comparison.",
)
async def compare_models(
    asset_id: int,
    db: DbSessionDep,
    user: CurrentUserDep,
    models: str = Query("yolov8n,yolov8s", description="Comma-separated model names"),
    confidence: float = Query(0.25, ge=0.0, le=1.0),
) -> dict:
    """
    Run detection with multiple models and compare results.

    Useful for A/B testing and model selection.
    """
    # Get the asset
    asset = await db.get(Asset, asset_id)
    if not asset or asset.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )

    # Parse models
    model_list = [m.strip() for m in models.split(",")]
    for m in model_list:
        if m not in MODEL_VARIANTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid model: {m}",
            )

    # Get file
    storage = get_storage_service()
    file_path = await storage.get_file_path(asset.storage_path)
    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    # Load image once
    image = Image.open(file_path)
    if image.mode != "RGB":
        image = image.convert("RGB")

    # Run detection with each model
    service = get_yolo_service()
    results = {}

    for model_name in model_list:
        result = service.detect(
            image=image,
            model_name=model_name,
            confidence_threshold=confidence,
        )
        results[model_name] = result.to_dict()

    return {
        "asset_id": asset_id,
        "comparison": results,
        "summary": {
            model: {
                "detections": len(results[model]["detections"]),
                "inference_time_ms": results[model]["metrics"]["inference_time_ms"],
            }
            for model in model_list
        },
    }


# =============================================================================
# Style Transfer Endpoints
# =============================================================================


@router.get(
    "/styles",
    summary="List available styles",
    description="Get information about available preset styles for style transfer.",
)
async def list_styles() -> dict:
    """
    List all available preset styles.

    Returns style names, artists, and preview URLs.
    """
    return {
        "presets": PRESET_STYLES,
    }


@router.get(
    "/style/{asset_id}",
    summary="Apply style transfer",
    description="Apply neural style transfer to an image.",
    responses={
        200: {
            "content": {"image/png": {}},
            "description": "Styled image",
        },
    },
)
async def apply_style(
    asset_id: int,
    db: DbSessionDep,
    user: CurrentUserOptionalDep = None,
    token: str | None = Query(None, description="JWT token for browser requests"),
    preset: str | None = Query(None, description="Preset style name"),
    style_url: str | None = Query(None, description="Custom style image URL"),
    alpha: float = Query(1.0, ge=0.0, le=1.0, description="Style strength (0=content, 1=full style)"),
    max_size: int = Query(512, ge=256, le=1024, description="Max image dimension"),
) -> Response:
    """
    Apply style transfer to an asset.

    Either provide a preset name OR a custom style URL.
    Uses fast neural style transfer with pre-trained models for presets.
    """
    # Handle token-based auth
    if not user and token:
        auth_service = AuthService(db)
        user_id = auth_service.verify_access_token(token)
        if user_id:
            user = await auth_service.get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    # Validate inputs
    if not preset and not style_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'preset' or 'style_url' must be provided",
        )

    if preset and preset not in PRESET_STYLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown preset: {preset}. Available: {list(PRESET_STYLES.keys())}",
        )

    # Get asset
    asset = await db.get(Asset, asset_id)
    if not asset or asset.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )

    # Get file
    storage = get_storage_service()
    file_path = await storage.get_file_path(asset.storage_path)
    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    # Load content image
    content_image = Image.open(file_path)
    if content_image.mode != "RGB":
        content_image = content_image.convert("RGB")

    # Apply style transfer
    service = get_style_service()

    try:
        if preset:
            result = service.transfer_preset(
                content=content_image,
                preset_name=preset,
                alpha=alpha,
                max_size=max_size,
            )
        else:
            result = service.transfer(
                content=content_image,
                style=style_url,
                alpha=alpha,
                max_size=max_size,
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Style transfer failed: {str(e)}",
        )

    return Response(
        content=result.image_bytes,
        media_type="image/png",
        headers={
            "X-Style": result.style_name,
            "X-Alpha": str(result.alpha),
            "X-Inference-Time-Ms": str(round(result.inference_time_ms, 2)),
            "X-Device": result.device,
        },
    )


@router.post(
    "/style/{asset_id}/with-image",
    summary="Apply custom style from uploaded image",
    description="Apply style transfer using an uploaded style image.",
    responses={
        200: {
            "content": {"image/png": {}},
            "description": "Styled image",
        },
    },
)
async def apply_custom_style(
    asset_id: int,
    db: DbSessionDep,
    user: CurrentUserDep,
    style_file: UploadFile = File(..., description="Style image to apply"),
    alpha: float = Query(1.0, ge=0.0, le=1.0, description="Style strength"),
    max_size: int = Query(256, ge=128, le=512, description="Max image dimension"),
) -> Response:
    """
    Apply style transfer using a custom uploaded style image.
    """
    # Get asset
    asset = await db.get(Asset, asset_id)
    if not asset or asset.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )

    # Get content file
    storage = get_storage_service()
    file_path = await storage.get_file_path(asset.storage_path)
    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    # Load images
    content_image = Image.open(file_path)
    if content_image.mode != "RGB":
        content_image = content_image.convert("RGB")

    style_content = await style_file.read()
    style_image = Image.open(io.BytesIO(style_content))
    if style_image.mode != "RGB":
        style_image = style_image.convert("RGB")

    # Apply style transfer
    service = get_style_service()

    try:
        result = service.transfer(
            content=content_image,
            style=style_image,
            alpha=alpha,
            max_size=max_size,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Style transfer failed: {str(e)}",
        )

    return Response(
        content=result.image_bytes,
        media_type="image/png",
        headers={
            "X-Style": "custom_upload",
            "X-Alpha": str(result.alpha),
            "X-Inference-Time-Ms": str(round(result.inference_time_ms, 2)),
            "X-Device": result.device,
        },
    )
