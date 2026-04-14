"""
Celery tasks package.

Import all task modules here to ensure they are registered with Celery.
"""

from app.workers.tasks.processing import (
    process_asset,
    extract_text_ocr,
    reprocess_failed_assets,
    batch_process_pending,
)

__all__ = [
    "process_asset",
    "extract_text_ocr",
    "reprocess_failed_assets",
    "batch_process_pending",
]
