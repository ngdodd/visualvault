# Similarity Search: Finding Related Images

## The Power of Embeddings

With CLIP embeddings, we can perform semantic search:

| Search Type | Query | Result |
|-------------|-------|--------|
| Text-to-Image | "a dog on the beach" | Images matching that description |
| Image-to-Image | Upload photo | Similar photos |
| Label Search | "dog" | Images classified as containing dogs |

---

## Vector Similarity

### Cosine Similarity

For normalized vectors, cosine similarity = dot product:

```python
import numpy as np

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """
    Compute cosine similarity between two vectors.

    For normalized vectors (length = 1):
    cosine_similarity = dot_product
    """
    # If already normalized
    return float(np.dot(a, b))

    # If not normalized
    # return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
```

### Why Normalization Matters

```python
# Without normalization: vectors of different lengths
emb1 = [0.5, 0.5, 0.5]  # length = 0.866
emb2 = [1.0, 1.0, 1.0]  # length = 1.732

# With normalization: all vectors have length 1
emb1_norm = [0.577, 0.577, 0.577]  # length = 1.0
emb2_norm = [0.577, 0.577, 0.577]  # length = 1.0

# Now dot product = cosine similarity
# Range: -1 (opposite) to 1 (identical)
```

---

## Text-to-Image Search

Find images that match a text description:

```python
@router.post("/search/text")
async def search_by_text(
    query: str,
    user: CurrentUserDep,
    db: DbSessionDep,
    limit: int = 20,
    min_similarity: float = 0.2,
):
    """
    Search images using natural language.

    Example queries:
    - "a photo of a dog"
    - "sunset over mountains"
    - "people at a restaurant"
    """
    # 1. Generate text embedding
    clip_service = get_clip_service()
    query_embedding = clip_service.get_text_embedding(query)

    # 2. Get all user's image embeddings
    assets_with_embeddings = await get_user_embeddings(db, user.id)

    # 3. Compute similarities
    results = []
    for asset, image_embedding in assets_with_embeddings:
        similarity = np.dot(query_embedding, image_embedding)
        if similarity >= min_similarity:
            results.append((asset, similarity))

    # 4. Sort by similarity (descending)
    results.sort(key=lambda x: x[1], reverse=True)

    # 5. Return top results
    return [
        {"asset": asset, "similarity": score}
        for asset, score in results[:limit]
    ]
```

### Query Tips

CLIP works best with descriptive phrases:

```python
# Good queries
"a photo of a golden retriever"
"sunset over the ocean"
"people eating pizza at a restaurant"
"modern architecture building"

# Less effective
"dog"  # Too vague
"pretty"  # Subjective
"IMG_2023"  # Not semantic
```

---

## Image-to-Image Search

Find images similar to a given image:

```python
@router.post("/search/similar/{asset_id}")
async def search_similar(
    asset_id: int,
    user: CurrentUserDep,
    db: DbSessionDep,
    limit: int = 20,
    min_similarity: float = 0.5,
):
    """Find images similar to a specific asset."""

    # 1. Get the query image's embedding
    query_asset = await db.get(Asset, asset_id)
    if not query_asset or query_asset.user_id != user.id:
        raise HTTPException(404, "Asset not found")

    query_embedding = np.array(json.loads(query_asset.embedding_vector))

    # 2. Compare with all other images
    all_assets = await get_user_embeddings(db, user.id)

    results = []
    for asset, embedding in all_assets:
        if asset.id == asset_id:
            continue  # Skip the query image itself

        similarity = np.dot(query_embedding, embedding)
        if similarity >= min_similarity:
            results.append((asset, similarity))

    # 3. Sort and return
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:limit]
```

---

## Search by Uploaded Image

Search without first uploading to the collection:

```python
@router.post("/search/image")
async def search_by_image(
    file: UploadFile,
    user: CurrentUserDep,
    db: DbSessionDep,
):
    """Upload an image to find similar images."""

    # 1. Validate uploaded image
    content = await file.read()
    image = Image.open(io.BytesIO(content))

    # 2. Generate embedding for uploaded image
    clip_service = get_clip_service()
    query_embedding = clip_service.get_image_embedding(image)

    # 3. Search user's collection
    all_assets = await get_user_embeddings(db, user.id)

    results = []
    for asset, embedding in all_assets:
        similarity = np.dot(query_embedding, embedding)
        results.append((asset, similarity))

    results.sort(key=lambda x: x[1], reverse=True)
    return results[:20]
```

---

## Label-Based Search

Search using ML-generated labels:

```python
@router.get("/search/labels")
async def search_by_label(
    label: str,
    user: CurrentUserDep,
    db: DbSessionDep,
):
    """Find images with specific labels."""

    # Get processed assets with labels
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
        labels = json.loads(asset.ml_labels)
        if any(label_lower in l.lower() for l in labels):
            matching.append(asset)

    return matching
```

---

## Efficient Vector Search

### Problem: Linear Scan

Comparing against all embeddings is O(n):

```python
# For 10,000 images: 10,000 dot products per search
for embedding in all_embeddings:
    similarity = np.dot(query, embedding)
```

### Solution: Approximate Nearest Neighbors (ANN)

For large collections, use ANN libraries:

```python
# Using FAISS (Facebook AI Similarity Search)
import faiss

# Build index (once, when embeddings change)
d = 512  # Embedding dimension
index = faiss.IndexFlatIP(d)  # Inner product (cosine for normalized)
index.add(np.array(embeddings))

# Search (fast!)
distances, indices = index.search(query_embedding.reshape(1, -1), k=10)
```

### When to Use ANN

| Collection Size | Approach |
|-----------------|----------|
| < 1,000 | Linear scan (fast enough) |
| 1,000 - 100,000 | Consider ANN |
| > 100,000 | Definitely use ANN |

Popular libraries:
- **FAISS** (Facebook) - Best performance
- **Annoy** (Spotify) - Easy to use
- **Hnswlib** - Good balance

---

## Search Results Schema

```python
from pydantic import BaseModel, Field

class SearchResult(BaseModel):
    asset: AssetResponse
    similarity: float = Field(..., ge=-1.0, le=1.0)


class SearchResults(BaseModel):
    results: list[SearchResult]
    query_type: str  # "text" or "image"
    total_searched: int
```

---

## Filtering Results

Combine semantic search with metadata filters:

```python
@router.post("/search/advanced")
async def advanced_search(
    query: str,
    user: CurrentUserDep,
    db: DbSessionDep,
    content_type: str | None = None,  # Filter by image type
    min_width: int | None = None,      # Minimum dimensions
    created_after: datetime | None = None,
):
    # Get filtered assets first
    stmt = select(Asset).where(
        Asset.user_id == user.id,
        Asset.status == AssetStatus.COMPLETED.value,
    )

    if content_type:
        stmt = stmt.where(Asset.content_type == content_type)
    if min_width:
        stmt = stmt.where(Asset.width >= min_width)
    if created_after:
        stmt = stmt.where(Asset.created_at >= created_after)

    result = await db.execute(stmt)
    assets = result.scalars().all()

    # Then do semantic search on filtered set
    query_embedding = clip_service.get_text_embedding(query)

    results = []
    for asset in assets:
        if asset.embedding_vector:
            embedding = np.array(json.loads(asset.embedding_vector))
            similarity = np.dot(query_embedding, embedding)
            results.append((asset, similarity))

    results.sort(key=lambda x: x[1], reverse=True)
    return results
```

---

## Best Practices

### 1. Normalize Embeddings

```python
# Always normalize before storing
embedding = embedding / np.linalg.norm(embedding)
```

### 2. Set Reasonable Thresholds

```python
# Too low = noisy results
min_similarity: float = 0.1  # Bad

# Good defaults
min_similarity: float = 0.3  # Text search
min_similarity: float = 0.5  # Image similarity
```

### 3. Limit Results

```python
# Don't return everything
return results[:20]  # Top 20
```

### 4. Handle Missing Embeddings

```python
for asset in assets:
    if not asset.embedding_vector:
        continue  # Skip unprocessed assets
```

### 5. Cache Embeddings

```python
# Load embeddings once, reuse
async def get_user_embeddings(db, user_id: int):
    # Consider caching this in Redis for frequent searchers
    pass
```

---

## Example: Complete Search Flow

```
User: "Show me photos of dogs at the beach"

1. API receives request
2. Generate text embedding for query
3. Load user's image embeddings from DB
4. Compute similarity for each image
5. Filter by minimum threshold (0.2)
6. Sort by similarity
7. Return top 20 results

Results:
- Asset #42 (dog playing in waves) - 0.78
- Asset #15 (puppy on sandy beach) - 0.72
- Asset #88 (beach sunset with dogs) - 0.65
- ...
```

---

## Further Reading

- [FAISS Documentation](https://github.com/facebookresearch/faiss)
- [Annoy (Spotify)](https://github.com/spotify/annoy)
- [Vector Search Explained](https://www.pinecone.io/learn/vector-search/)
