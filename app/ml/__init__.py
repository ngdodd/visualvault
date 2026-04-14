"""
Machine Learning components package.

This package contains ML model services and utilities:
- CLIP for image embeddings and zero-shot classification
- Future: OCR service
- Future: Object detection
"""

from app.ml.clip_service import CLIPService, get_clip_service, init_clip_service

__all__ = [
    "CLIPService",
    "get_clip_service",
    "init_clip_service",
]
