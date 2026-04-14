# Celery Tasks: Writing Background Jobs

## Defining Tasks

### Basic Task

```python
from celery import shared_task

@shared_task
def add(x: int, y: int) -> int:
    """A simple task that adds two numbers."""
    return x + y
```

### Task with Options

```python
@shared_task(
    bind=True,                    # First arg is task instance
    name="custom.task.name",      # Custom task name
    queue="ml",                   # Default queue
    time_limit=300,               # Hard time limit (seconds)
    soft_time_limit=240,          # Soft limit (raises exception)
    max_retries=3,                # Maximum retry attempts
    default_retry_delay=60,       # Delay between retries
    autoretry_for=(Exception,),   # Auto-retry for these exceptions
    retry_backoff=True,           # Exponential backoff
    retry_backoff_max=600,        # Max backoff delay
    acks_late=True,               # Acknowledge after completion
)
def process_asset(self, asset_id: int) -> dict:
    """Process an uploaded asset with ML."""
    pass
```

---

## `@shared_task` vs `@app.task`

```python
from celery import shared_task, Celery

app = Celery()

# Bound to specific app
@app.task
def task1():
    pass

# Works with any app (recommended for reusable code)
@shared_task
def task2():
    pass
```

Use `@shared_task` when:
- Tasks are in a separate module
- Code might be used with different Celery apps
- You want better testability

---

## Calling Tasks

### Synchronous (Blocking)

```python
# Run immediately (testing/development)
result = add(2, 3)  # Returns 5

# With eager mode
# celery_app.conf.task_always_eager = True
result = add.delay(2, 3).get()  # Runs sync, returns 5
```

### Asynchronous (Non-blocking)

```python
# Send to queue and continue
result = add.delay(2, 3)  # Returns AsyncResult immediately
# Task runs in worker

# Or with explicit syntax
result = add.apply_async(args=[2, 3])

# Check if done
if result.ready():
    print(result.get())  # Get result (blocks if not ready)
```

### Advanced Options

```python
result = add.apply_async(
    args=[2, 3],
    kwargs={"extra": "data"},
    countdown=60,          # Delay execution by 60 seconds
    eta=datetime(2024, 1, 1, 12, 0),  # Run at specific time
    expires=3600,          # Expire if not run within 1 hour
    queue="high-priority", # Specific queue
    priority=0,            # 0-9, lower = higher priority
)
```

---

## Task States

```
PENDING → STARTED → SUCCESS
              ↓
           FAILURE
              ↓
           RETRY
```

```python
result = process_asset.delay(asset_id=1)

result.state    # 'PENDING', 'STARTED', 'SUCCESS', 'FAILURE', 'RETRY'
result.ready()  # True if finished (success or failure)
result.successful()  # True if succeeded
result.failed()  # True if failed
result.result   # Return value (if success) or exception (if failure)
result.traceback  # Traceback string (if failure)
```

---

## Accessing Task Instance

Use `bind=True` to access the task instance:

```python
@shared_task(bind=True)
def process_with_retry(self, asset_id: int):
    try:
        # Do work
        pass
    except TemporaryError as e:
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))

    # Task info
    self.request.id          # Task UUID
    self.request.retries     # Current retry count
    self.request.args        # Positional args
    self.request.kwargs      # Keyword args
```

---

## Retry Handling

### Manual Retry

```python
@shared_task(bind=True, max_retries=3)
def unreliable_task(self, url: str):
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise self.retry(
            exc=exc,
            countdown=60,  # Wait 60 seconds
        )
```

### Automatic Retry

```python
@shared_task(
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,       # Exponential backoff: 1, 2, 4, 8...
    retry_backoff_max=600,    # Cap at 10 minutes
    retry_kwargs={"max_retries": 5},
)
def auto_retry_task():
    # Automatically retries on ConnectionError or TimeoutError
    pass
```

### Retry Backoff

```
retry_backoff=True + retry_backoff_max=600

Attempt 1: Immediate
Attempt 2: Wait 1 second
Attempt 3: Wait 2 seconds
Attempt 4: Wait 4 seconds
Attempt 5: Wait 8 seconds
...
Maximum: Wait 600 seconds (10 minutes)
```

---

## Error Handling

### Handle in Task

```python
@shared_task(bind=True)
def process_asset(self, asset_id: int):
    try:
        asset = load_asset(asset_id)
        result = do_processing(asset)
        update_asset_status(asset, "completed")
        return {"status": "success", "result": result}

    except AssetNotFound:
        # Don't retry - asset doesn't exist
        return {"status": "error", "message": "Asset not found"}

    except TemporaryError as e:
        # Retry this
        update_asset_status(asset, "retrying")
        raise self.retry(exc=e)

    except Exception as e:
        # Permanent failure
        update_asset_status(asset, "failed", error=str(e))
        raise  # Re-raise for Celery to mark as FAILURE
```

### Error Callbacks

```python
@shared_task
def on_task_error(request, exc, traceback):
    """Called when a task fails."""
    print(f"Task {request.id} failed: {exc}")
    send_alert_email(f"Task failed: {exc}")

# Attach callback
result = process_asset.apply_async(
    args=[1],
    link_error=on_task_error.s()
)
```

---

## Our Processing Task

```python
# app/workers/tasks/processing.py

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
    Main processing task for uploaded images.

    1. Load image from storage
    2. Generate CLIP embedding
    3. Extract labels via zero-shot classification
    4. Extract dominant colors
    5. Update database with results
    """
    logger.info(f"Processing asset {asset_id}")

    with get_sync_db_session() as db:
        asset = db.get(Asset, asset_id)
        if not asset:
            return {"error": "Asset not found"}

        # Update status
        asset.status = AssetStatus.PROCESSING.value
        db.commit()

        try:
            # Load image
            image = Image.open(storage_path)

            # Get CLIP service (lazy loading)
            clip = get_clip_service()

            # Generate embedding
            embedding = clip.get_image_embedding(image)
            asset.embedding_vector = json.dumps(embedding.tolist())

            # Zero-shot classification
            labels = clip.classify_image(image, DEFAULT_LABELS)
            asset.ml_labels = json.dumps([l for l, s in labels[:5] if s > 0.05])

            # Extract colors
            colors = extract_dominant_colors(image)
            asset.ml_colors = json.dumps(colors)

            # Mark completed
            asset.status = AssetStatus.COMPLETED.value
            asset.processed_at = datetime.now(timezone.utc)
            db.commit()

            return {"status": "completed", "asset_id": asset_id}

        except Exception as e:
            asset.status = AssetStatus.FAILED.value
            asset.error_message = str(e)
            db.commit()
            raise  # Re-raise for retry/failure handling
```

---

## Task Signatures

Chain tasks together:

```python
from celery import chain, group, chord

# Chain: Run tasks in sequence
chain(
    process_asset.s(asset_id),
    extract_text_ocr.s(),
    update_search_index.s(),
)()

# Group: Run tasks in parallel
group(
    process_asset.s(1),
    process_asset.s(2),
    process_asset.s(3),
)()

# Chord: Parallel tasks + callback when all complete
chord(
    [process_asset.s(i) for i in asset_ids],
    finalize_batch.s()
)()
```

### Partial Signatures

```python
# Create partial signature
sig = process_asset.s(asset_id=1)

# Add options
sig = sig.set(countdown=60, queue="ml")

# Execute
result = sig.delay()
```

---

## Task Progress

Report progress for long-running tasks:

```python
@shared_task(bind=True)
def process_batch(self, asset_ids: list):
    total = len(asset_ids)

    for i, asset_id in enumerate(asset_ids):
        process_single_asset(asset_id)

        # Update progress
        self.update_state(
            state="PROGRESS",
            meta={"current": i + 1, "total": total}
        )

    return {"processed": total}


# Check progress
result = process_batch.delay([1, 2, 3, 4, 5])

while not result.ready():
    if result.state == "PROGRESS":
        info = result.info
        print(f"Progress: {info['current']}/{info['total']}")
    time.sleep(1)
```

---

## Testing Tasks

### Eager Mode

```python
# conftest.py
@pytest.fixture(autouse=True)
def celery_eager(settings):
    """Run tasks synchronously in tests."""
    from app.workers.celery_app import celery_app
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    yield
    celery_app.conf.task_always_eager = False
```

### Unit Testing

```python
def test_process_asset(db_session, sample_asset):
    # Run synchronously due to eager mode
    result = process_asset.delay(sample_asset.id)

    assert result.get()["status"] == "completed"

    # Verify database updated
    db_session.refresh(sample_asset)
    assert sample_asset.status == AssetStatus.COMPLETED.value
    assert sample_asset.embedding_vector is not None
```

---

## Best Practices

### 1. Idempotency

```python
# Bad: Creates duplicates on retry
@shared_task
def process(asset_id):
    Result.create(asset_id=asset_id, data="processed")

# Good: Safe to retry
@shared_task
def process(asset_id):
    Result.update_or_create(asset_id=asset_id, data="processed")
```

### 2. Small Arguments

```python
# Bad: Passing large data
@shared_task
def process(image_bytes):  # Megabytes!
    pass

# Good: Pass references
@shared_task
def process(asset_id):
    asset = load_asset(asset_id)
    image = load_image(asset.storage_path)
```

### 3. Timeouts

```python
@shared_task(
    time_limit=300,        # Kill after 5 min
    soft_time_limit=240,   # Raise exception after 4 min
)
def process(asset_id):
    try:
        long_operation()
    except SoftTimeLimitExceeded:
        # Cleanup and save partial results
        save_partial_results()
        raise
```

### 4. Late Acknowledgment

```python
@shared_task(acks_late=True)
def critical_task():
    # If worker dies, task will be requeued
    pass
```

---

## Further Reading

- [Celery Task Guide](https://docs.celeryq.dev/en/stable/userguide/tasks.html)
- [Canvas: Designing Workflows](https://docs.celeryq.dev/en/stable/userguide/canvas.html)
- [Task Best Practices](https://docs.celeryq.dev/en/stable/userguide/tasks.html#best-practices)
