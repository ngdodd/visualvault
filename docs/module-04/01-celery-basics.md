# Celery Basics: Distributed Task Queue

## Why Background Processing?

Some operations are too slow for HTTP requests:

| Operation | Time | User Experience |
|-----------|------|-----------------|
| Database query | 10ms | ✅ Instant |
| File upload | 500ms | ✅ Acceptable |
| ML inference | 2-30s | ❌ Too slow |
| Video processing | Minutes | ❌ Way too slow |

**Solution:** Return immediately, process in background.

```
Without background processing:
User → Upload Image → Wait 5s for ML → Response
                      (User stares at spinner)

With background processing:
User → Upload Image → Immediate Response → Processing happens async
                      (User continues working)
```

---

## What is Celery?

Celery is a distributed task queue for Python:

- **Distributed**: Tasks run on separate worker processes/machines
- **Async**: Fire-and-forget, or wait for results
- **Reliable**: Retries, acknowledgments, persistence
- **Scalable**: Add more workers as needed

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Your Application                         │
└─────────────────────────────────────────────────────────────────┘
                               │
                               │ 1. Send task
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Message Broker (Redis)                       │
│                                                                  │
│  Queue: default    Queue: ml         Queue: email               │
│  ┌─────────────┐  ┌─────────────┐   ┌─────────────┐            │
│  │ task1       │  │ process_img │   │ send_email  │            │
│  │ task2       │  │ process_img │   │             │            │
│  │ task3       │  │             │   │             │            │
│  └─────────────┘  └─────────────┘   └─────────────┘            │
└─────────────────────────────────────────────────────────────────┘
                               │
                               │ 2. Workers fetch tasks
                               ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Worker 1   │  │   Worker 2   │  │   Worker 3   │
│   (CPU)      │  │   (GPU)      │  │   (CPU)      │
│              │  │              │  │              │
│  Processes   │  │  Processes   │  │  Processes   │
│  default     │  │  ml queue    │  │  email       │
└──────────────┘  └──────────────┘  └──────────────┘
                               │
                               │ 3. Store results (optional)
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Result Backend (Redis)                        │
│                                                                  │
│  Results stored temporarily for retrieval                        │
└─────────────────────────────────────────────────────────────────┘
```

**Components:**

1. **Broker**: Message queue (Redis, RabbitMQ)
2. **Workers**: Processes that execute tasks
3. **Result Backend**: Stores task results (optional)

---

## Celery Application

```python
# app/workers/celery_app.py

from celery import Celery
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "visualvault",  # App name
    broker=settings.redis.url,  # Message broker URL
    backend=settings.redis.url,  # Result backend URL
    include=[  # Task modules to load
        "app.workers.tasks.processing",
    ],
)
```

### Configuration Options

```python
celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Task execution
    task_time_limit=300,         # Hard limit: 5 minutes
    task_soft_time_limit=240,    # Soft limit: 4 minutes (raises exception)

    # Worker settings
    worker_concurrency=4,        # Number of worker processes
    worker_prefetch_multiplier=1,  # Tasks to prefetch (1 = fair distribution)

    # Result settings
    result_expires=3600,  # Results expire after 1 hour

    # Reliability
    task_acks_late=True,  # Acknowledge after completion (not before)
    task_reject_on_worker_lost=True,  # Requeue if worker dies
)
```

---

## Task Routing

Route different tasks to different queues:

```python
celery_app.conf.task_routes = {
    # ML tasks go to ml queue
    "app.workers.tasks.processing.*": {"queue": "ml"},

    # Email tasks go to email queue
    "app.workers.tasks.email.*": {"queue": "email"},

    # Everything else goes to default
}

celery_app.conf.task_default_queue = "default"
```

**Running workers for specific queues:**

```bash
# Worker for ML tasks only
celery -A app.workers.celery_app worker -Q ml

# Worker for all queues
celery -A app.workers.celery_app worker -Q default,ml,email
```

---

## Redis as Broker

Redis is a popular choice for Celery:

**Pros:**
- Fast (in-memory)
- Simple to set up
- Also works as result backend
- Supports pub/sub for real-time updates

**Cons:**
- Messages lost if Redis crashes (unless persistence enabled)
- Less feature-rich than RabbitMQ

**Connection URL:**
```
redis://[:password]@host:port/db_number

redis://localhost:6379/0
redis://:secretpassword@redis.example.com:6379/0
```

---

## Eager Mode (Testing)

For testing, run tasks synchronously:

```python
celery_app.conf.update(
    task_always_eager=True,  # Run tasks immediately (no worker needed)
    task_eager_propagates=True,  # Propagate exceptions
)
```

```python
# In tests
def test_process_asset():
    # This runs synchronously, no worker needed
    result = process_asset.delay(asset_id=1)
    assert result.get() == {"status": "completed"}
```

---

## Starting Workers

### Command Line

```bash
# Basic worker
celery -A app.workers.celery_app worker --loglevel=info

# With specific concurrency
celery -A app.workers.celery_app worker -c 4 --loglevel=info

# Specific queues
celery -A app.workers.celery_app worker -Q ml --loglevel=info

# With beat scheduler (periodic tasks)
celery -A app.workers.celery_app worker --beat --loglevel=info
```

### Docker Compose

```yaml
# docker-compose.yml
services:
  worker:
    build: .
    command: celery -A app.workers.celery_app worker -l info
    environment:
      - REDIS_HOST=redis
      - DB_HOST=db
    depends_on:
      - redis
      - db
```

---

## Worker Lifecycle

```
1. STARTUP
   - Connect to broker
   - Load task modules
   - Initialize worker pool

2. RUNNING
   - Fetch tasks from queue
   - Execute tasks
   - Send results to backend
   - Acknowledge completion

3. SHUTDOWN (graceful)
   - Stop fetching new tasks
   - Finish current tasks
   - Close connections
```

### Graceful Shutdown

```bash
# Graceful shutdown (wait for tasks)
celery -A app.workers.celery_app control shutdown

# Or send SIGTERM
kill -TERM <worker_pid>

# Immediate shutdown (tasks lost!)
kill -9 <worker_pid>
```

---

## Monitoring with Flower

Flower provides a web UI for monitoring:

```bash
# Install
pip install flower

# Run
celery -A app.workers.celery_app flower --port=5555

# Open http://localhost:5555
```

**Features:**
- Real-time task monitoring
- Worker status
- Task history
- Rate limiting controls
- Remote worker control

---

## Best Practices

### 1. Keep Tasks Small

```python
# Bad: One huge task
@shared_task
def process_everything():
    for asset in get_all_assets():
        process_image(asset)
        extract_text(asset)
        generate_embedding(asset)

# Good: Small, focused tasks
@shared_task
def process_asset(asset_id: int):
    # Process one asset
    pass
```

### 2. Make Tasks Idempotent

```python
# Bad: Not idempotent (creates duplicates on retry)
@shared_task
def create_user(email):
    User.create(email=email)

# Good: Idempotent (safe to retry)
@shared_task
def create_user(email):
    User.get_or_create(email=email)
```

### 3. Don't Pass Large Objects

```python
# Bad: Passing large data
@shared_task
def process_image(image_bytes):  # Could be megabytes!
    pass

# Good: Pass IDs, load in worker
@shared_task
def process_image(asset_id):
    asset = load_asset(asset_id)
    image = load_from_storage(asset.storage_path)
```

### 4. Handle Database Connections

```python
# Celery workers are separate processes
# Can't share async connections from API

def get_sync_session():
    """Use sync SQLAlchemy in workers."""
    engine = create_engine(settings.database.url_sync)
    return Session(engine)
```

---

## Common Issues

### "Task received but not executed"

Check that:
1. Task module is in `include` list
2. Worker is listening to correct queue
3. No import errors in task module

### "Connection refused"

Check:
1. Redis is running
2. `REDIS_HOST` environment variable is set
3. Network connectivity between worker and Redis

### "Task always times out"

Increase time limits:
```python
@shared_task(time_limit=600)  # 10 minutes
def long_running_task():
    pass
```

---

## Further Reading

- [Celery Getting Started](https://docs.celeryq.dev/en/stable/getting-started/introduction.html)
- [Celery Best Practices](https://docs.celeryq.dev/en/stable/userguide/tasks.html#best-practices)
- [Redis as Broker](https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/redis.html)
