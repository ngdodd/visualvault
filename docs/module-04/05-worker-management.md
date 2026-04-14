# Worker Management: Running Celery in Production

## Starting Workers

### Basic Worker

```bash
celery -A app.workers.celery_app worker --loglevel=info
```

### With Options

```bash
celery -A app.workers.celery_app worker \
    --loglevel=info \
    --concurrency=4 \           # Number of worker processes
    --queues=default,ml \       # Queues to consume
    --hostname=worker1@%h       # Worker name
```

### Worker for ML Tasks

```bash
# Dedicated ML worker (GPU machine)
celery -A app.workers.celery_app worker \
    -Q ml \
    -c 1 \                      # One process (GPU can't parallelize well)
    --loglevel=info
```

---

## Docker Compose Setup

```yaml
# docker-compose.yml

services:
  api:
    build: .
    ports:
      - "8000:8000"
    depends_on:
      - db
      - redis

  worker:
    build: .
    command: celery -A app.workers.celery_app worker -l info
    environment:
      - REDIS_HOST=redis
      - DB_HOST=db
      - ML_DEVICE=cpu
    depends_on:
      - redis
      - db
    volumes:
      - ./storage:/app/storage

  worker-ml:
    build: .
    command: celery -A app.workers.celery_app worker -Q ml -c 1 -l info
    environment:
      - REDIS_HOST=redis
      - DB_HOST=db
      - ML_DEVICE=cuda
    depends_on:
      - redis
      - db
    volumes:
      - ./storage:/app/storage
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: visualvault
      POSTGRES_USER: visualvault
      POSTGRES_PASSWORD: visualvault
```

---

## Concurrency Settings

### Worker Processes

```python
# Number of parallel worker processes
celery_app.conf.worker_concurrency = 4
```

```bash
# Or via command line
celery -A app.workers.celery_app worker -c 4
```

### For ML Tasks

```python
# ML tasks are memory/GPU intensive
# Usually 1 process per GPU
celery_app.conf.worker_concurrency = 1  # For ML workers
```

### Prefetch Multiplier

```python
# How many tasks to prefetch per worker
celery_app.conf.worker_prefetch_multiplier = 1  # For long tasks
celery_app.conf.worker_prefetch_multiplier = 4  # For quick tasks
```

`prefetch=1` ensures fair distribution for long-running tasks.

---

## Queue Configuration

### Define Queues

```python
celery_app.conf.task_routes = {
    "app.workers.tasks.processing.*": {"queue": "ml"},
    "app.workers.tasks.email.*": {"queue": "email"},
    # Default queue for everything else
}

celery_app.conf.task_default_queue = "default"
```

### Run Workers for Specific Queues

```bash
# General worker
celery -A app.workers.celery_app worker -Q default -c 4

# ML worker
celery -A app.workers.celery_app worker -Q ml -c 1

# All queues
celery -A app.workers.celery_app worker -Q default,ml,email -c 4
```

---

## Monitoring with Flower

Flower provides a real-time web UI:

```bash
# Install
pip install flower

# Run
celery -A app.workers.celery_app flower --port=5555

# With authentication
celery -A app.workers.celery_app flower \
    --port=5555 \
    --basic_auth=admin:password
```

### Docker Compose

```yaml
flower:
  image: mher/flower
  command: celery --broker=redis://redis:6379/0 flower
  ports:
    - "5555:5555"
  depends_on:
    - redis
```

### Flower Features

- Real-time task monitoring
- Worker status and control
- Task history and details
- Queue lengths
- Rate limiting
- Remote worker shutdown/restart

---

## Health Checks

### Check Worker Status

```bash
# Ping workers
celery -A app.workers.celery_app inspect ping

# List active tasks
celery -A app.workers.celery_app inspect active

# Queue lengths
celery -A app.workers.celery_app inspect reserved

# Worker stats
celery -A app.workers.celery_app inspect stats
```

### Health Endpoint

```python
# app/api/v1/health.py

from app.workers.celery_app import celery_app

@router.get("/worker-health")
async def worker_health():
    """Check if Celery workers are running."""
    try:
        # Ping workers with timeout
        result = celery_app.control.ping(timeout=1.0)
        if result:
            return {
                "status": "healthy",
                "workers": len(result),
                "details": result,
            }
        else:
            return {
                "status": "unhealthy",
                "error": "No workers responded",
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
        }
```

---

## Graceful Shutdown

### Signal Handling

```bash
# Warm shutdown (finish current tasks)
kill -TERM <worker_pid>
# Or
celery -A app.workers.celery_app control shutdown

# Cold shutdown (stop immediately, tasks requeued if acks_late=True)
kill -QUIT <worker_pid>
```

### Docker Compose

```bash
# Graceful stop
docker-compose stop worker

# With timeout
docker-compose stop -t 60 worker
```

### Kubernetes

```yaml
spec:
  terminationGracePeriodSeconds: 120  # Wait for tasks to finish
  containers:
    - name: worker
      lifecycle:
        preStop:
          exec:
            command: ["celery", "-A", "app.workers.celery_app", "control", "shutdown"]
```

---

## Scaling Workers

### Horizontal Scaling

```bash
# Start multiple workers
docker-compose up --scale worker=4
```

### Auto-scaling

Monitor queue length and scale workers:

```python
# Check queue length
from redis import Redis

redis = Redis(host="localhost")
queue_length = redis.llen("celery")

if queue_length > 100:
    # Scale up (implementation depends on infrastructure)
    scale_workers(count=8)
elif queue_length < 10:
    scale_workers(count=2)
```

---

## Logging

### Configure Logging

```python
celery_app.conf.update(
    worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
    worker_task_log_format="[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s",
)
```

### Log to File

```bash
celery -A app.workers.celery_app worker \
    --loglevel=info \
    --logfile=/var/log/celery/worker.log
```

### Structured Logging

```python
import structlog

logger = structlog.get_logger(__name__)

@shared_task(bind=True)
def process_asset(self, asset_id: int):
    logger.info(
        "Processing asset",
        asset_id=asset_id,
        task_id=self.request.id,
    )
```

---

## Error Handling

### Dead Letter Queue

```python
# Tasks that fail too many times
celery_app.conf.task_reject_on_worker_lost = True

@shared_task(bind=True, max_retries=3)
def risky_task(self):
    try:
        # ... work ...
    except Exception as e:
        if self.request.retries >= self.max_retries:
            # Move to dead letter queue
            send_to_dlq(self.request.id, str(e))
            raise
        raise self.retry(exc=e, countdown=60)
```

### Alert on Failures

```python
from celery.signals import task_failure

@task_failure.connect
def handle_task_failure(sender, task_id, exception, args, kwargs, traceback, einfo, **kw):
    """Send alert when a task fails."""
    send_slack_alert(
        f"Task {sender.name} failed: {exception}",
        task_id=task_id,
    )
```

---

## Production Checklist

### Configuration

- [ ] `acks_late=True` for critical tasks
- [ ] Reasonable `time_limit` and `soft_time_limit`
- [ ] Appropriate `max_retries`
- [ ] `retry_backoff=True` for transient failures

### Infrastructure

- [ ] Redis persistence enabled (AOF or RDB)
- [ ] Worker health checks
- [ ] Graceful shutdown configured
- [ ] Logging to external system

### Monitoring

- [ ] Flower or similar monitoring
- [ ] Queue length alerts
- [ ] Task failure alerts
- [ ] Worker memory monitoring

### Security

- [ ] Redis password set
- [ ] Flower authentication enabled
- [ ] Workers in private network

---

## Troubleshooting

### "No workers available"

```bash
# Check if workers are running
celery -A app.workers.celery_app inspect ping

# Check broker connection
celery -A app.workers.celery_app inspect report
```

### "Tasks stuck in queue"

```bash
# Check queue lengths
celery -A app.workers.celery_app inspect reserved

# Purge queue (dangerous!)
celery -A app.workers.celery_app purge
```

### "Worker memory growing"

```python
# Restart worker after N tasks
celery_app.conf.worker_max_tasks_per_child = 100

# Or use memory limit
celery_app.conf.worker_max_memory_per_child = 200000  # 200MB
```

### "Tasks restarting constantly"

```python
# Check for:
# 1. Exceptions not being handled
# 2. Time limits too short
# 3. Worker dying (OOM)

# Enable task events for debugging
celery -A app.workers.celery_app worker -l debug --events
```

---

## Further Reading

- [Celery Workers Guide](https://docs.celeryq.dev/en/stable/userguide/workers.html)
- [Flower Documentation](https://flower.readthedocs.io/)
- [Celery Monitoring](https://docs.celeryq.dev/en/stable/userguide/monitoring.html)
- [Production Deployment](https://docs.celeryq.dev/en/stable/userguide/daemonizing.html)
