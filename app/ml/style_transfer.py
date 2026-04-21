"""
Fast Neural Style Transfer Service

Uses pre-trained feed-forward networks for real-time style transfer.
Much faster and better quality than optimization-based approaches.

Pre-trained models based on Johnson et al. "Perceptual Losses for Real-Time Style Transfer"
"""

import io
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import torch
import torch.nn as nn
import numpy as np
from PIL import Image
from torchvision import transforms

from app.config import get_settings
from app.ml.transformer_net import TransformerNet

logger = logging.getLogger(__name__)


@dataclass
class StyleTransferResult:
    """Result of style transfer operation."""
    image_bytes: bytes
    content_size: tuple[int, int]
    style_name: str
    alpha: float
    inference_time_ms: float
    device: str


# Pre-trained style models - these are trained on specific famous artworks
# Models from PyTorch examples: https://github.com/pytorch/examples/tree/main/fast_neural_style
# Dropbox archive: https://www.dropbox.com/s/lrvwfehqdcxoza8/saved_models.zip
PRESET_STYLES = {
    "mosaic": {
        "name": "Mosaic",
        "artist": "Abstract",
        "description": "Colorful geometric mosaic pattern",
    },
    "candy": {
        "name": "Candy",
        "artist": "Abstract",
        "description": "Vibrant candy-colored style",
    },
    "rain_princess": {
        "name": "Rain Princess",
        "artist": "Leonid Afremov",
        "description": "Colorful impressionist rain scene",
    },
    "udnie": {
        "name": "Udnie",
        "artist": "Francis Picabia",
        "description": "Abstract cubist artwork",
    },
}

# Direct download URLs from Dropbox (extracted from the zip)
MODEL_URLS = {
    "mosaic": "https://www.dropbox.com/s/hpcz94eevpepre8/mosaic.pth?dl=1",
    "candy": "https://www.dropbox.com/s/00xyjlwjt5mnhk4/candy.pth?dl=1",
    "rain_princess": "https://www.dropbox.com/s/lruwkzj5v1s26vy/rain_princess.pth?dl=1",
    "udnie": "https://www.dropbox.com/s/olvhjpuh3j10l8o/udnie.pth?dl=1",
}


class StyleTransferService:
    """Fast Neural Style Transfer using pre-trained models."""

    def __init__(self):
        self.device: torch.device | None = None
        self.models: dict[str, TransformerNet] = {}
        self.models_dir: Path | None = None
        self._initialized = False

    def initialize(self) -> None:
        if self._initialized:
            return

        settings = get_settings()

        if settings.ml.device == "cuda" and torch.cuda.is_available():
            self.device = torch.device("cuda")
        elif settings.ml.device == "mps" and torch.backends.mps.is_available():
            self.device = torch.device("mps")
        else:
            self.device = torch.device("cpu")

        logger.info(f"Style Transfer using {self.device}")

        # Create models directory
        self.models_dir = Path("/app/models/style_transfer")
        self.models_dir.mkdir(parents=True, exist_ok=True)

        self._initialized = True
        logger.info("Style Transfer service initialized")

    def _ensure_initialized(self):
        if not self._initialized:
            self.initialize()

    def _download_model(self, style_name: str) -> Path:
        """Download pre-trained model weights."""
        import httpx

        model_path = self.models_dir / f"{style_name}.pth"

        if model_path.exists():
            logger.info(f"Model {style_name} already downloaded")
            return model_path

        if style_name not in MODEL_URLS:
            raise ValueError(f"No download URL for style: {style_name}")

        url = MODEL_URLS[style_name]

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

        try:
            logger.info(f"Downloading {style_name} model from Dropbox...")
            with httpx.Client(follow_redirects=True, timeout=120.0, headers=headers) as client:
                response = client.get(url)
                response.raise_for_status()

                with open(model_path, "wb") as f:
                    f.write(response.content)

                logger.info(f"Downloaded {style_name} model ({len(response.content) / 1024 / 1024:.1f} MB)")
                return model_path
        except Exception as e:
            logger.error(f"Failed to download {style_name}: {e}")
            raise RuntimeError(f"Failed to download model for {style_name}: {e}")

    def _load_model(self, style_name: str) -> TransformerNet:
        """Load a pre-trained style model."""
        if style_name in self.models:
            return self.models[style_name]

        model_path = self._download_model(style_name)

        model = TransformerNet()

        # Load state dict (weights_only=False needed for older PyTorch model format)
        # These are trusted models from PyTorch examples
        state_dict = torch.load(str(model_path), map_location=self.device, weights_only=False)

        # Handle different state dict formats
        # Some models have keys without the module prefix
        # Also filter out running_mean/running_var from old PyTorch InstanceNorm
        new_state_dict = {}
        for key, value in state_dict.items():
            # Remove 'module.' prefix if present (from DataParallel)
            new_key = key.replace("module.", "")
            # Skip running stats from old InstanceNorm (pre-0.4.0 format)
            if "running_mean" in new_key or "running_var" in new_key or "num_batches_tracked" in new_key:
                continue
            new_state_dict[new_key] = value

        model.load_state_dict(new_state_dict, strict=False)
        model.to(self.device)
        model.eval()

        self.models[style_name] = model
        logger.info(f"Loaded {style_name} model")
        return model

    def _load_image(self, source: Image.Image | BinaryIO, max_size: int) -> torch.Tensor:
        """Load and preprocess image."""
        if isinstance(source, Image.Image):
            image = source
        else:
            image = Image.open(source)

        if image.mode != 'RGB':
            image = image.convert('RGB')

        # Resize if needed
        w, h = image.size
        scale = max_size / max(w, h)
        if scale < 1:
            image = image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        # Convert to tensor
        transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Lambda(lambda x: x.mul(255))  # Scale to 0-255
        ])
        return transform(image).unsqueeze(0).to(self.device)

    def _tensor_to_image(self, tensor: torch.Tensor) -> Image.Image:
        """Convert tensor to PIL Image."""
        tensor = tensor.squeeze(0).cpu().clamp(0, 255)
        array = tensor.permute(1, 2, 0).numpy().astype(np.uint8)
        return Image.fromarray(array)

    def transfer_preset(
        self,
        content: Image.Image | BinaryIO,
        preset_name: str,
        alpha: float = 1.0,
        max_size: int = 512,
    ) -> StyleTransferResult:
        """Apply preset style using pre-trained fast neural style model."""
        self._ensure_initialized()

        if preset_name not in PRESET_STYLES:
            raise ValueError(f"Unknown preset: {preset_name}. Available: {list(PRESET_STYLES.keys())}")

        start_time = time.time()

        # Load model
        model = self._load_model(preset_name)

        # Load and preprocess content image
        content_tensor = self._load_image(content, max_size)
        content_size = (content_tensor.shape[3], content_tensor.shape[2])

        # Run style transfer
        with torch.no_grad():
            styled_tensor = model(content_tensor)

        # Apply alpha blending if needed
        if alpha < 1.0:
            styled_tensor = alpha * styled_tensor + (1 - alpha) * content_tensor

        # Convert to image
        output_image = self._tensor_to_image(styled_tensor)

        # Save to bytes
        buffer = io.BytesIO()
        output_image.save(buffer, format='PNG')
        image_bytes = buffer.getvalue()

        return StyleTransferResult(
            image_bytes=image_bytes,
            content_size=content_size,
            style_name=PRESET_STYLES[preset_name]["name"],
            alpha=alpha,
            inference_time_ms=(time.time() - start_time) * 1000,
            device=str(self.device),
        )

    def transfer(
        self,
        content: Image.Image | BinaryIO,
        style: Image.Image | BinaryIO | str,
        alpha: float = 1.0,
        max_size: int = 512,
        num_steps: int = 50,
    ) -> StyleTransferResult:
        """
        Apply arbitrary style transfer using optimization.

        For custom styles not in presets, falls back to Gatys optimization.
        """
        self._ensure_initialized()
        start_time = time.time()

        # Import VGG for optimization-based transfer
        from torchvision.models import vgg19, VGG19_Weights
        import torch.nn.functional as F
        import torch.optim as optim

        def gram_matrix(tensor: torch.Tensor) -> torch.Tensor:
            b, c, h, w = tensor.size()
            features = tensor.view(b, c, h * w)
            gram = torch.bmm(features, features.transpose(1, 2))
            return gram / (c * h * w)

        # Load VGG features
        vgg = vgg19(weights=VGG19_Weights.IMAGENET1K_V1).features.to(self.device).eval()
        for param in vgg.parameters():
            param.requires_grad = False

        # Get feature layers
        style_layers = [0, 5, 10, 19, 28]
        content_layer = 21

        def get_features(x, layers):
            features = []
            for i, layer in enumerate(vgg):
                x = layer(x)
                if i in layers:
                    features.append(x)
                if i == max(layers):
                    break
            return features

        # Normalize for VGG
        mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1).to(self.device)
        std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1).to(self.device)

        # Load images
        content_tensor = self._load_image(content, max_size) / 255.0
        content_tensor = (content_tensor - mean) / std

        if isinstance(style, str):
            import httpx
            with httpx.Client(follow_redirects=True, timeout=30.0) as client:
                response = client.get(style)
                response.raise_for_status()
                style_image = Image.open(io.BytesIO(response.content))
        elif isinstance(style, Image.Image):
            style_image = style
        else:
            style_image = Image.open(style)

        style_tensor = self._load_image(style_image, max_size) / 255.0
        style_tensor = (style_tensor - mean) / std

        if style_tensor.shape[2:] != content_tensor.shape[2:]:
            style_tensor = F.interpolate(style_tensor, size=content_tensor.shape[2:], mode='bilinear', align_corners=False)

        content_size = (content_tensor.shape[3], content_tensor.shape[2])

        # Get target features
        with torch.no_grad():
            content_features = get_features(content_tensor, [content_layer])
            style_features = get_features(style_tensor, style_layers)
            style_grams = [gram_matrix(f) for f in style_features]

        # Optimize
        output = content_tensor.clone().requires_grad_(True)
        optimizer = optim.Adam([output], lr=0.03)

        for step in range(num_steps):
            optimizer.zero_grad()

            output_content = get_features(output, [content_layer])
            output_style = get_features(output, style_layers)

            content_loss = F.mse_loss(output_content[0], content_features[0])

            style_loss = 0
            for of, sg in zip(output_style, style_grams):
                style_loss += F.mse_loss(gram_matrix(of), sg)
            style_loss /= len(style_layers)

            loss = content_loss + 1e6 * alpha * style_loss
            loss.backward()
            optimizer.step()

        # Convert back
        output = output * std + mean
        output = output.clamp(0, 1) * 255
        output_image = self._tensor_to_image(output.detach())

        buffer = io.BytesIO()
        output_image.save(buffer, format='PNG')
        image_bytes = buffer.getvalue()

        return StyleTransferResult(
            image_bytes=image_bytes,
            content_size=content_size,
            style_name="custom",
            alpha=alpha,
            inference_time_ms=(time.time() - start_time) * 1000,
            device=str(self.device),
        )

    def get_available_presets(self) -> dict:
        return PRESET_STYLES


_style_service: StyleTransferService | None = None


def get_style_service() -> StyleTransferService:
    global _style_service
    if _style_service is None:
        _style_service = StyleTransferService()
    return _style_service


def init_style_service() -> StyleTransferService:
    global _style_service
    _style_service = StyleTransferService()
    _style_service.initialize()
    return _style_service
