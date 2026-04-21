"""
Asset Processing Tasks

This module contains Celery tasks for processing uploaded assets:
- Image feature extraction (CLIP embeddings)
- Label generation (zero-shot classification)
- Color extraction
- OCR text extraction

Tasks are designed to be idempotent and handle failures gracefully.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from celery import shared_task
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.asset import Asset, AssetStatus
from app.models.tag import UserTag
from app.ml.clip_service import get_clip_service
from app.utils.image import extract_dominant_colors

logger = logging.getLogger(__name__)

# Common labels for zero-shot classification
DEFAULT_LABELS = [
    "person", "people", "portrait", "selfie",
    "animal", "dog", "cat", "bird", "wildlife",
    "landscape", "nature", "mountain", "beach", "forest", "ocean",
    "city", "building", "architecture", "street",
    "food", "meal", "restaurant",
    "vehicle", "car", "airplane",
    "art", "painting", "illustration",
    "document", "text", "screenshot",
    "product", "fashion", "clothing",
    "sports", "outdoors", "indoor",
]


def get_sync_db_session() -> Session:
    """
    Get a synchronous database session for Celery tasks.

    Celery tasks run in separate processes and can't use async code easily,
    so we use synchronous SQLAlchemy here.
    """
    settings = get_settings()
    engine = create_engine(settings.database.url_sync)
    return Session(engine)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_kwargs={"max_retries": 3},
    acks_late=True,
)
def process_asset(self, asset_id: int) -> dict:
    """
    Main task for processing an uploaded asset.

    This task:
    1. Loads the image from storage
    2. Generates CLIP embedding
    3. Performs zero-shot classification
    4. Extracts dominant colors
    5. Updates the database with results

    Args:
        asset_id: ID of the asset to process

    Returns:
        Dictionary with processing results
    """
    logger.info(f"Processing asset {asset_id}")
    settings = get_settings()

    with get_sync_db_session() as db:
        # Get the asset
        asset = db.get(Asset, asset_id)
        if not asset:
            logger.error(f"Asset {asset_id} not found")
            return {"error": "Asset not found"}

        # Update status to processing
        asset.status = AssetStatus.PROCESSING.value
        db.commit()

        try:
            # Load the image
            storage_path = settings.storage.uploads_path / asset.storage_path
            if not storage_path.exists():
                raise FileNotFoundError(f"File not found: {storage_path}")

            image = Image.open(storage_path)

            # Convert to RGB if necessary
            if image.mode != "RGB":
                image = image.convert("RGB")

            # Get CLIP service (lazy initialization)
            clip_service = get_clip_service()

            # Generate embedding
            logger.info(f"Generating embedding for asset {asset_id}")
            embedding = clip_service.get_image_embedding(image)
            asset.embedding_vector = json.dumps(embedding.tolist())

            # Zero-shot classification
            # Combine default labels with user's custom tags
            logger.info(f"Classifying asset {asset_id}")

            # Fetch user's custom tags
            user_tags = db.query(UserTag).filter(
                UserTag.user_id == asset.user_id
            ).all()
            custom_tag_names = [tag.name for tag in user_tags]

            # Combine labels, prioritizing custom tags
            all_labels = list(set(custom_tag_names + DEFAULT_LABELS))
            logger.info(f"Using {len(all_labels)} labels ({len(custom_tag_names)} custom)")

            classifications = clip_service.classify_image(image, all_labels)
            # Take top 5 labels with confidence > 0.05
            top_labels = [
                label for label, score in classifications[:10]
                if score > 0.05
            ][:5]
            asset.ml_labels = json.dumps(top_labels)

            # Extract colors
            logger.info(f"Extracting colors for asset {asset_id}")
            with open(storage_path, "rb") as f:
                colors = extract_dominant_colors(f, num_colors=5)
            asset.ml_colors = json.dumps(colors)

            # Update status to completed
            asset.status = AssetStatus.COMPLETED.value
            asset.processed_at = datetime.now(timezone.utc)
            asset.error_message = None
            db.commit()

            logger.info(f"Asset {asset_id} processed successfully")
            return {
                "asset_id": asset_id,
                "status": "completed",
                "labels": top_labels,
                "colors": len(colors),
                "embedding_dim": len(embedding),
            }

        except Exception as e:
            logger.exception(f"Error processing asset {asset_id}: {e}")

            # Update status to failed
            asset.status = AssetStatus.FAILED.value
            asset.error_message = str(e)
            db.commit()

            # Re-raise for Celery retry
            raise


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 2},
)
def extract_text_ocr(self, asset_id: int) -> dict:
    """
    Extract text from an image using OCR.

    This is a separate task because OCR can be slow and is optional.
    Uses EasyOCR for text detection and recognition.

    Args:
        asset_id: ID of the asset to process

    Returns:
        Dictionary with extracted text
    """
    logger.info(f"Running OCR on asset {asset_id}")
    settings = get_settings()

    try:
        import easyocr
    except ImportError:
        logger.warning("EasyOCR not installed, skipping OCR")
        return {"error": "EasyOCR not installed"}

    with get_sync_db_session() as db:
        asset = db.get(Asset, asset_id)
        if not asset:
            return {"error": "Asset not found"}

        try:
            storage_path = settings.storage.uploads_path / asset.storage_path

            # Initialize EasyOCR reader
            reader = easyocr.Reader(["en"], gpu=settings.ml.device == "cuda")

            # Run OCR
            results = reader.readtext(str(storage_path))

            # Extract text with confidence > 0.5
            texts = [text for (_, text, conf) in results if conf > 0.5]
            extracted_text = " ".join(texts) if texts else None

            # Update asset
            asset.ml_text = extracted_text
            db.commit()

            logger.info(f"OCR completed for asset {asset_id}: {len(texts)} text regions")
            return {
                "asset_id": asset_id,
                "text_regions": len(texts),
                "text_preview": extracted_text[:100] if extracted_text else None,
            }

        except Exception as e:
            logger.exception(f"OCR error for asset {asset_id}: {e}")
            return {"error": str(e)}


@shared_task
def reprocess_failed_assets() -> dict:
    """
    Find and requeue failed assets for processing.

    This can be run periodically to retry failed assets.
    """
    logger.info("Checking for failed assets to reprocess")

    with get_sync_db_session() as db:
        # Find failed assets
        failed_assets = db.query(Asset).filter(
            Asset.status == AssetStatus.FAILED.value
        ).all()

        requeued = 0
        for asset in failed_assets:
            # Reset status and requeue
            asset.status = AssetStatus.PENDING.value
            asset.error_message = None
            process_asset.delay(asset.id)
            requeued += 1

        db.commit()

        logger.info(f"Requeued {requeued} failed assets")
        return {"requeued": requeued}


@shared_task
def batch_process_pending() -> dict:
    """
    Process all pending assets.

    Useful for catching up after a worker was down.
    """
    logger.info("Processing pending assets")

    with get_sync_db_session() as db:
        pending_assets = db.query(Asset).filter(
            Asset.status == AssetStatus.PENDING.value
        ).all()

        queued = 0
        for asset in pending_assets:
            process_asset.delay(asset.id)
            queued += 1

        logger.info(f"Queued {queued} pending assets")
        return {"queued": queued}
