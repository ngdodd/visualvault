# CLIP Embeddings: Semantic Image Understanding

## What is CLIP?

CLIP (Contrastive Language-Image Pre-Training) is a neural network trained on 400 million image-text pairs from the internet. It learns to understand both images and text in a shared embedding space.

**Key capabilities:**
- Generate embeddings for images
- Generate embeddings for text
- Compare images to images
- Compare images to text
- Zero-shot classification

---

## How CLIP Works

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIP Model                               │
│                                                                  │
│  ┌──────────────┐                    ┌──────────────┐           │
│  │ Image Encoder│                    │ Text Encoder │           │
│  │ (ViT/ResNet) │                    │ (Transformer)│           │
│  └──────┬───────┘                    └──────┬───────┘           │
│         │                                   │                    │
│         ▼                                   ▼                    │
│  ┌──────────────┐                    ┌──────────────┐           │
│  │   512-dim    │                    │   512-dim    │           │
│  │  embedding   │ ◄─── Same space ──►│  embedding   │           │
│  └──────────────┘                    └──────────────┘           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

Images and text are mapped to the SAME vector space!

Similar concepts → Similar vectors
Dog photo ≈ "a photo of a dog"
```

---

## Training Objective

CLIP was trained with contrastive learning:

```
Batch of (image, text) pairs:

     Image₁  Image₂  Image₃  ...
Text₁  ✓       ✗       ✗
Text₂  ✗       ✓       ✗
Text₃  ✗       ✗       ✓
...

✓ = high similarity (correct pair)
✗ = low similarity (wrong pair)

The model learns to maximize similarity for correct pairs
and minimize it for incorrect pairs.
```

---

## Loading CLIP

```python
# app/ml/clip_service.py

from transformers import CLIPModel, CLIPProcessor
import torch

class CLIPService:
    def __init__(self):
        self.model = None
        self.processor = None
        self.device = None
        self._initialized = False

    def initialize(self):
        """Load model (call once, reuse many times)."""
        if self._initialized:
            return

        model_name = "openai/clip-vit-base-patch32"

        # Choose device
        if torch.cuda.is_available():
            self.device = torch.device("cuda")
        elif torch.backends.mps.is_available():
            self.device = torch.device("mps")
        else:
            self.device = torch.device("cpu")

        # Load model and processor
        self.processor = CLIPProcessor.from_pretrained(model_name)
        self.model = CLIPModel.from_pretrained(model_name)
        self.model.to(self.device)
        self.model.eval()  # Inference mode

        self._initialized = True
```

### Model Variants

| Model | Parameters | Embedding Dim | Speed | Quality |
|-------|------------|---------------|-------|---------|
| `clip-vit-base-patch32` | 151M | 512 | Fast | Good |
| `clip-vit-base-patch16` | 149M | 512 | Medium | Better |
| `clip-vit-large-patch14` | 428M | 768 | Slow | Best |

---

## Generating Image Embeddings

```python
from PIL import Image
import numpy as np

def get_image_embedding(self, image: Image.Image) -> np.ndarray:
    """
    Generate a 512-dimensional embedding for an image.

    The embedding captures semantic meaning:
    - Objects in the image
    - Scene type
    - Colors and style
    - Actions and relationships
    """
    self.ensure_initialized()

    # Preprocess: resize, normalize, convert to tensor
    inputs = self.processor(images=image, return_tensors="pt")
    inputs = {k: v.to(self.device) for k, v in inputs.items()}

    # Generate embedding (no gradient computation needed)
    with torch.no_grad():
        image_features = self.model.get_image_features(**inputs)

    # Convert to numpy and normalize
    embedding = image_features.cpu().numpy()[0]
    embedding = embedding / np.linalg.norm(embedding)

    return embedding  # Shape: (512,)
```

### Why Normalize?

```python
# Normalized vectors have length 1
# This makes dot product = cosine similarity

embedding = embedding / np.linalg.norm(embedding)

# Now: np.dot(emb1, emb2) gives similarity from -1 to 1
```

---

## Generating Text Embeddings

```python
def get_text_embedding(self, text: str) -> np.ndarray:
    """
    Generate embedding for a text query.

    Examples:
    - "a photo of a dog"
    - "sunset over the ocean"
    - "people eating at a restaurant"
    """
    self.ensure_initialized()

    # Preprocess text
    inputs = self.processor(text=[text], return_tensors="pt", padding=True)
    inputs = {k: v.to(self.device) for k, v in inputs.items()}

    with torch.no_grad():
        text_features = self.model.get_text_features(**inputs)

    embedding = text_features.cpu().numpy()[0]
    embedding = embedding / np.linalg.norm(embedding)

    return embedding
```

---

## Computing Similarity

```python
def compute_similarity(emb1: np.ndarray, emb2: np.ndarray) -> float:
    """
    Compute cosine similarity between normalized embeddings.

    For normalized vectors:
    cosine_similarity = dot_product

    Returns: -1 (opposite) to 1 (identical)
    """
    return float(np.dot(emb1, emb2))
```

### Interpreting Similarity Scores

| Score | Meaning |
|-------|---------|
| 0.9+ | Nearly identical |
| 0.7-0.9 | Very similar |
| 0.5-0.7 | Related |
| 0.3-0.5 | Somewhat related |
| 0.0-0.3 | Unrelated |
| <0.0 | Opposite |

---

## Zero-Shot Classification

Classify images without training on specific labels:

```python
def classify_image(
    self,
    image: Image.Image,
    labels: list[str],
) -> list[tuple[str, float]]:
    """
    Classify an image into one of the provided labels.

    Works by comparing image embedding to text embeddings
    of "a photo of {label}" for each label.
    """
    # Create prompts
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

        # Normalize
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)

        # Compute similarities
        similarities = (image_features @ text_features.T).squeeze(0)

        # Convert to probabilities
        probs = torch.softmax(similarities * 100, dim=0)

    # Return sorted results
    results = list(zip(labels, probs.cpu().numpy().tolist()))
    results.sort(key=lambda x: x[1], reverse=True)

    return results
```

### Example Usage

```python
labels = ["dog", "cat", "bird", "car", "building", "nature"]
results = clip_service.classify_image(image, labels)

# Results:
# [("dog", 0.85), ("nature", 0.08), ("cat", 0.03), ...]
```

---

## Batch Processing

Process multiple images efficiently:

```python
def get_image_embeddings_batch(
    self,
    images: list[Image.Image],
    batch_size: int = 8,
) -> list[np.ndarray]:
    """Process multiple images in batches."""
    self.ensure_initialized()

    all_embeddings = []

    for i in range(0, len(images), batch_size):
        batch = images[i:i + batch_size]

        # Preprocess batch
        inputs = self.processor(images=batch, return_tensors="pt", padding=True)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            features = self.model.get_image_features(**inputs)

        # Normalize each embedding
        embeddings = features.cpu().numpy()
        for emb in embeddings:
            normalized = emb / np.linalg.norm(emb)
            all_embeddings.append(normalized)

    return all_embeddings
```

---

## Storage and Retrieval

### Storing Embeddings

```python
import json

# Store as JSON string in database
embedding = clip_service.get_image_embedding(image)
asset.embedding_vector = json.dumps(embedding.tolist())
```

### Loading Embeddings

```python
# Load from database
embedding = np.array(json.loads(asset.embedding_vector))
```

### Binary Storage (More Efficient)

```python
import numpy as np

# Store as bytes
embedding_bytes = embedding.astype(np.float32).tobytes()

# Load from bytes
embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
```

---

## Performance Optimization

### 1. Lazy Loading

```python
_clip_service: CLIPService | None = None

def get_clip_service() -> CLIPService:
    global _clip_service
    if _clip_service is None:
        _clip_service = CLIPService()
        _clip_service.initialize()
    return _clip_service
```

### 2. GPU Acceleration

```python
# 10-100x faster than CPU!
if torch.cuda.is_available():
    self.device = torch.device("cuda")
```

### 3. Batch Processing

```python
# Bad: One image at a time
for image in images:
    emb = clip_service.get_image_embedding(image)

# Good: Batch processing
embeddings = clip_service.get_image_embeddings_batch(images, batch_size=16)
```

### 4. Mixed Precision

```python
# Use float16 for faster inference on GPU
with torch.cuda.amp.autocast():
    features = self.model.get_image_features(**inputs)
```

---

## Common Issues

### "CUDA out of memory"

```python
# Reduce batch size
batch_size = 4  # Instead of 16

# Or clear cache
torch.cuda.empty_cache()
```

### "Model loading is slow"

```python
# Cache models locally
export TRANSFORMERS_CACHE=/path/to/cache

# Or pre-download
from transformers import CLIPModel
CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
```

### "Inconsistent results"

```python
# Ensure eval mode and no gradients
self.model.eval()
with torch.no_grad():
    features = self.model.get_image_features(**inputs)
```

---

## Further Reading

- [CLIP Paper](https://arxiv.org/abs/2103.00020)
- [OpenAI CLIP](https://openai.com/research/clip)
- [Hugging Face CLIP](https://huggingface.co/docs/transformers/model_doc/clip)
- [CLIP Applications](https://github.com/openai/CLIP)
