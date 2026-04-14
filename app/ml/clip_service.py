"""
CLIP Model Service

This module provides image embedding generation using OpenAI's CLIP model.
CLIP (Contrastive Language-Image Pre-Training) creates embeddings that
capture semantic meaning, enabling similarity search and zero-shot classification.

Features:
- Image embedding generation (512D vectors)
- Text embedding for search queries
- Batch processing support
- GPU acceleration when available
"""

import logging
from pathlib import Path
from typing import List

import numpy as np
import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class CLIPService:
    """
    Service for generating CLIP embeddings.

    CLIP embeddings allow us to:
    1. Find visually similar images
    2. Search images using text descriptions
    3. Zero-shot image classification
    """

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.model: CLIPModel | None = None
        self.processor: CLIPProcessor | None = None
        self.device: torch.device | None = None
        self._initialized = False

    def initialize(self) -> None:
        """
        Load the CLIP model and processor.

        This is called lazily on first use or explicitly during startup.
        Loading is separate from __init__ to allow for lazy initialization.
        """
        if self._initialized:
            return

        model_name = self.settings.ml.clip_model_name
        logger.info(f"Loading CLIP model: {model_name}")

        # Determine device
        if self.settings.ml.device == "cuda" and torch.cuda.is_available():
            self.device = torch.device("cuda")
            logger.info("Using CUDA for inference")
        elif self.settings.ml.device == "mps" and torch.backends.mps.is_available():
            self.device = torch.device("mps")
            logger.info("Using MPS (Apple Silicon) for inference")
        else:
            self.device = torch.device("cpu")
            logger.info("Using CPU for inference")

        # Load model and processor
        self.processor = CLIPProcessor.from_pretrained(model_name)
        self.model = CLIPModel.from_pretrained(model_name)
        self.model.to(self.device)
        self.model.eval()  # Set to evaluation mode

        self._initialized = True
        logger.info("CLIP model loaded successfully")

    def ensure_initialized(self) -> None:
        """Ensure the model is initialized before use."""
        if not self._initialized:
            self.initialize()

    def get_image_embedding(self, image: Image.Image) -> np.ndarray:
        """
        Generate embedding for a single image.

        Args:
            image: PIL Image object

        Returns:
            Normalized embedding vector (512D numpy array)
        """
        self.ensure_initialized()

        # Preprocess image
        inputs = self.processor(images=image, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # Generate embedding
        with torch.no_grad():
            image_features = self.model.get_image_features(**inputs)

        # Handle both tensor and BaseModelOutputWithPooling return types
        if hasattr(image_features, 'pooler_output'):
            image_features = image_features.pooler_output
        elif hasattr(image_features, 'last_hidden_state'):
            image_features = image_features.last_hidden_state[:, 0, :]

        # Normalize the embedding
        embedding = image_features.cpu().numpy()[0]
        embedding = embedding / np.linalg.norm(embedding)

        return embedding

    def get_image_embeddings_batch(
        self,
        images: List[Image.Image],
        batch_size: int | None = None,
    ) -> List[np.ndarray]:
        """
        Generate embeddings for multiple images.

        Args:
            images: List of PIL Image objects
            batch_size: Batch size for processing (default from settings)

        Returns:
            List of normalized embedding vectors
        """
        self.ensure_initialized()

        if batch_size is None:
            batch_size = self.settings.ml.batch_size

        all_embeddings = []

        for i in range(0, len(images), batch_size):
            batch = images[i:i + batch_size]

            # Preprocess batch
            inputs = self.processor(images=batch, return_tensors="pt", padding=True)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            # Generate embeddings
            with torch.no_grad():
                image_features = self.model.get_image_features(**inputs)

            # Handle both tensor and BaseModelOutputWithPooling return types
            if hasattr(image_features, 'pooler_output'):
                image_features = image_features.pooler_output
            elif hasattr(image_features, 'last_hidden_state'):
                image_features = image_features.last_hidden_state[:, 0, :]

            # Normalize each embedding
            embeddings = image_features.cpu().numpy()
            for emb in embeddings:
                normalized = emb / np.linalg.norm(emb)
                all_embeddings.append(normalized)

        return all_embeddings

    def get_text_embedding(self, text: str) -> np.ndarray:
        """
        Generate embedding for a text query.

        This allows searching images using natural language.

        Args:
            text: Search query (e.g., "a photo of a dog on the beach")

        Returns:
            Normalized embedding vector (512D numpy array)
        """
        self.ensure_initialized()

        # Preprocess text
        inputs = self.processor(text=[text], return_tensors="pt", padding=True)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # Generate embedding
        with torch.no_grad():
            text_features = self.model.get_text_features(**inputs)

        # Handle both tensor and output object return types
        if hasattr(text_features, 'pooler_output'):
            text_features = text_features.pooler_output
        elif hasattr(text_features, 'last_hidden_state'):
            text_features = text_features.last_hidden_state[:, 0, :]

        # Normalize
        embedding = text_features.cpu().numpy()[0]
        embedding = embedding / np.linalg.norm(embedding)

        return embedding

    def compute_similarity(
        self,
        embedding1: np.ndarray,
        embedding2: np.ndarray,
    ) -> float:
        """
        Compute cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Similarity score between -1 and 1 (higher is more similar)
        """
        # Since embeddings are normalized, dot product = cosine similarity
        return float(np.dot(embedding1, embedding2))

    def find_similar(
        self,
        query_embedding: np.ndarray,
        candidate_embeddings: List[np.ndarray],
        top_k: int = 10,
    ) -> List[tuple[int, float]]:
        """
        Find most similar embeddings to a query.

        Args:
            query_embedding: The embedding to search for
            candidate_embeddings: List of embeddings to search through
            top_k: Number of results to return

        Returns:
            List of (index, similarity_score) tuples, sorted by similarity
        """
        similarities = []
        for i, candidate in enumerate(candidate_embeddings):
            score = self.compute_similarity(query_embedding, candidate)
            similarities.append((i, score))

        # Sort by similarity (descending) and take top k
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]

    def classify_image(
        self,
        image: Image.Image,
        labels: List[str],
    ) -> List[tuple[str, float]]:
        """
        Zero-shot image classification.

        Classify an image into one of the provided labels without
        any training on those specific labels.

        Args:
            image: PIL Image to classify
            labels: List of possible labels

        Returns:
            List of (label, probability) tuples, sorted by probability
        """
        self.ensure_initialized()

        # Create text prompts for each label
        prompts = [f"a photo of {label}" for label in labels]

        # Get image embedding
        image_inputs = self.processor(images=image, return_tensors="pt")
        image_inputs = {k: v.to(self.device) for k, v in image_inputs.items()}

        # Get text embeddings
        text_inputs = self.processor(text=prompts, return_tensors="pt", padding=True)
        text_inputs = {k: v.to(self.device) for k, v in text_inputs.items()}

        with torch.no_grad():
            image_features = self.model.get_image_features(**image_inputs)
            text_features = self.model.get_text_features(**text_inputs)

            # Handle both tensor and output object return types
            if hasattr(image_features, 'pooler_output'):
                image_features = image_features.pooler_output
            elif hasattr(image_features, 'last_hidden_state'):
                image_features = image_features.last_hidden_state[:, 0, :]

            if hasattr(text_features, 'pooler_output'):
                text_features = text_features.pooler_output
            elif hasattr(text_features, 'last_hidden_state'):
                text_features = text_features.last_hidden_state[:, 0, :]

            # Normalize
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)

            # Compute similarities
            similarities = (image_features @ text_features.T).squeeze(0)

            # Convert to probabilities with softmax
            probs = torch.softmax(similarities * 100, dim=0)

        # Create result list
        results = list(zip(labels, probs.cpu().numpy().tolist()))
        results.sort(key=lambda x: x[1], reverse=True)

        return results

    def unload(self) -> None:
        """Unload model to free memory."""
        if self.model:
            del self.model
            self.model = None
        if self.processor:
            del self.processor
            self.processor = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        self._initialized = False
        logger.info("CLIP model unloaded")


# Global service instance
_clip_service: CLIPService | None = None


def get_clip_service() -> CLIPService:
    """Get the global CLIP service instance."""
    global _clip_service
    if _clip_service is None:
        _clip_service = CLIPService()
    return _clip_service


def init_clip_service(settings: Settings | None = None) -> CLIPService:
    """Initialize the CLIP service (call during startup)."""
    global _clip_service
    _clip_service = CLIPService(settings)
    _clip_service.initialize()
    return _clip_service
