# Module 4: Background Processing & ML Integration

## Overview

This module adds asynchronous task processing with Celery and integrates machine learning models for image analysis. By the end, uploaded images will be automatically processed to extract features, generate embeddings, and enable semantic search.

## Learning Objectives

By completing this module, you will be able to:

1. **Configure Celery** - Set up a distributed task queue with Redis
2. **Create background tasks** - Process work asynchronously
3. **Integrate ML models** - Load and use CLIP for embeddings
4. **Implement semantic search** - Find images by text or similarity
5. **Handle task failures** - Retry logic and error handling
6. **Monitor task queues** - Track processing status

---

## Prerequisites

- Completed Module 3 (File Uploads)
- Docker containers running (`docker-compose up -d`)
- Migrations applied (`alembic upgrade head`)
- Basic understanding of async programming

---

## Lesson Plan

### Part 1: Celery Fundamentals (20 min)

**Concepts:**
- What is a task queue?
- Celery architecture (broker, workers, results)
- When to use background processing

**Key Code:** `app/workers/celery_app.py`

```python
from celery import Celery

celery_app = Celery(
    "visualvault",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0",
    include=["app.workers.tasks.processing"],
)

celery_app.conf.update(
    task_serializer="json",
    task_time_limit=300,
    worker_concurrency=2,
)
```

**Key Takeaway:** Celery allows you to offload heavy work (ML inference) to separate worker processes, keeping your API responsive.

**Read More:** [01-celery-basics.md](./01-celery-basics.md)

---

### Part 2: Creating Tasks (25 min)

**Concepts:**
- Task decorators and options
- Passing arguments
- Retry policies
- Task states and results

**Key Code:** `app/workers/tasks/processing.py`

```python
from celery import shared_task

@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def process_asset(self, asset_id: int) -> dict:
    """Process an uploaded image."""
    # Load image
    # Generate embedding
    # Extract features
    # Update database
    return {"status": "completed", "asset_id": asset_id}
```

**Key Takeaway:** Tasks should be idempotent (safe to retry) and handle failures gracefully with exponential backoff.

**Read More:** [02-celery-tasks.md](./02-celery-tasks.md)

---

### Part 3: CLIP Model Integration (30 min)

**Concepts:**
- What is CLIP?
- Loading transformer models
- Image embeddings
- Text embeddings
- Zero-shot classification

**Key Code:** `app/ml/clip_service.py`

```python
from transformers import CLIPModel, CLIPProcessor

class CLIPService:
    def __init__(self):
        self.model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        self.processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

    def get_image_embedding(self, image: Image) -> np.ndarray:
        inputs = self.processor(images=image, return_tensors="pt")
        with torch.no_grad():
            features = self.model.get_image_features(**inputs)
        embedding = features.cpu().numpy()[0]
        return embedding / np.linalg.norm(embedding)
```

**Key Takeaway:** CLIP creates embeddings that capture semantic meaning, allowing us to compare images and text in the same vector space.

**Read More:** [03-clip-embeddings.md](./03-clip-embeddings.md)

---

### Part 4: Similarity Search (25 min)

**Concepts:**
- Cosine similarity
- Text-to-image search
- Image-to-image search
- Efficient vector comparison

**Key Code:** `app/api/v1/search.py`

```python
@router.post("/text")
async def search_by_text(query: str, user: CurrentUserDep, db: DbSessionDep):
    # Generate text embedding
    clip = get_clip_service()
    query_embedding = clip.get_text_embedding(query)

    # Compare with all user's image embeddings
    results = []
    for asset, embedding in get_user_embeddings(db, user.id):
        similarity = np.dot(query_embedding, embedding)
        results.append((asset, similarity))

    # Sort by similarity
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:20]
```

**Key Takeaway:** Normalized embeddings allow fast similarity computation using dot product (equivalent to cosine similarity).

**Read More:** [04-similarity-search.md](./04-similarity-search.md)

---

### Part 5: Worker Management (15 min)

**Concepts:**
- Starting workers
- Concurrency settings
- Monitoring with Flower
- Graceful shutdown

**Commands:**

```bash
# Start a worker
celery -A app.workers.celery_app worker --loglevel=info

# Start with specific queue
celery -A app.workers.celery_app worker -Q ml --loglevel=info

# Monitor with Flower
celery -A app.workers.celery_app flower --port=5555
```

**Read More:** [05-worker-management.md](./05-worker-management.md)

---

## Hands-On Exercises

### Exercise 1: Start Workers and Process an Image

```bash
# Terminal 1: Start the worker
docker-compose exec worker celery -A app.workers.celery_app worker -l info

# Terminal 2: Upload an image
TOKEN="your-token"
curl -X POST http://localhost:8000/api/v1/assets/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@photo.jpg"

# Watch the worker process it!
```

### Exercise 2: Search by Text

```bash
# Search for images
curl -X POST http://localhost:8000/api/v1/search/text \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "a photo of a dog"}'
```

### Exercise 3: Find Similar Images

```bash
# Get similar images to asset #1
curl -X POST http://localhost:8000/api/v1/search/similar/1 \
  -H "Authorization: Bearer $TOKEN"
```

### Exercise 4: Monitor Tasks

```bash
# Start Flower monitoring
docker-compose exec worker celery -A app.workers.celery_app flower

# Open http://localhost:5555 in browser
```

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `app/workers/celery_app.py` | Celery configuration |
| `app/workers/tasks/processing.py` | ML processing tasks |
| `app/ml/clip_service.py` | CLIP model service |
| `app/api/v1/search.py` | Search endpoints |

---

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/v1/search/text` | Yes | Search by text description |
| POST | `/api/v1/search/similar/{id}` | Yes | Find similar images |
| POST | `/api/v1/search/image` | Yes | Search by uploading an image |
| GET | `/api/v1/search/labels?label=dog` | Yes | Search by ML label |

---

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   FastAPI   │────►│    Redis    │◄────│   Worker    │
│   (API)     │     │   (Broker)  │     │  (Celery)   │
└─────────────┘     └─────────────┘     └─────────────┘
      │                                        │
      │                                        │
      ▼                                        ▼
┌─────────────┐                         ┌─────────────┐
│  PostgreSQL │                         │ CLIP Model  │
│    (DB)     │                         │   (ML)      │
└─────────────┘                         └─────────────┘
```

1. User uploads image → API saves to storage & DB
2. API sends task to Redis queue
3. Worker picks up task from queue
4. Worker loads image, runs ML model
5. Worker updates DB with results
6. User can search using embeddings

---

## Common Issues & Solutions

### "Worker not picking up tasks"
**Cause:** Worker not connected to correct Redis/queue.
**Solution:** Check `REDIS_HOST` env var and queue names.

### "CUDA out of memory"
**Cause:** GPU memory exhausted.
**Solution:** Reduce batch size or use CPU (`ML_DEVICE=cpu`).

### "Task timeout"
**Cause:** Processing takes too long.
**Solution:** Increase `task_time_limit` or optimize model loading.

### "Model loading on every task"
**Cause:** Model not cached.
**Solution:** Use lazy initialization with singleton pattern.

---

## Performance Tips

1. **Lazy load models** - Don't load at import time
2. **Reuse model instances** - Load once, use many times
3. **Batch when possible** - Process multiple images together
4. **Use GPU if available** - 10-100x faster than CPU
5. **Prefetch smartly** - `worker_prefetch_multiplier=1` for ML tasks

---

## What's Next: Module 5

In Module 5, we'll add:
- **Rate limiting** with SlowAPI
- **Caching** with Redis
- **API monitoring** and metrics
- **Production deployment** considerations

---

## Additional Resources

- [Celery Documentation](https://docs.celeryq.dev/)
- [CLIP Paper](https://arxiv.org/abs/2103.00020)
- [Hugging Face Transformers](https://huggingface.co/docs/transformers/)
- [Redis Documentation](https://redis.io/docs/)
