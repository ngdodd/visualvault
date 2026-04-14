# Request Logging: Observability for APIs

## Why Structured Logging?

Traditional logging:
```
[2024-01-15 10:30:00] INFO: Request to /api/v1/assets from 192.168.1.1
[2024-01-15 10:30:01] INFO: Response 200 in 150ms
```

Structured logging:
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "info",
  "event": "request_completed",
  "method": "GET",
  "path": "/api/v1/assets",
  "status_code": 200,
  "duration_ms": 150,
  "client_ip": "192.168.1.1",
  "correlation_id": "abc-123-def"
}
```

**Benefits:**
- Machine parseable
- Easy to filter and search
- Consistent format
- Rich context

---

## Structlog Setup

```python
# app/main.py

import structlog

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        # JSON in production, pretty print in dev
        structlog.processors.JSONRenderer()
        if settings.environment == "production"
        else structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)
```

---

## Request Logging Middleware

```python
# app/middleware/logging.py

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Generate correlation ID
        correlation_id = request.headers.get(
            "X-Correlation-ID",
            str(uuid.uuid4())
        )
        request.state.correlation_id = correlation_id

        # Start timing
        start_time = time.perf_counter()

        # Log request start
        logger.info(
            "Request started",
            method=request.method,
            path=request.url.path,
            correlation_id=correlation_id,
            client_ip=self._get_client_ip(request),
        )

        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Log completion
            logger.info(
                "Request completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
                correlation_id=correlation_id,
            )

            # Add headers
            response.headers["X-Correlation-ID"] = correlation_id
            response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

            return response

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "Request failed",
                method=request.method,
                path=request.url.path,
                error=str(e),
                duration_ms=round(duration_ms, 2),
                correlation_id=correlation_id,
            )
            raise
```

---

## Correlation IDs

Track requests across services:

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│   Client    │─────►│     API     │─────►│   Worker    │
│             │      │             │      │             │
│  X-Corr-ID: │      │  Log with   │      │  Log with   │
│  abc-123    │      │  abc-123    │      │  abc-123    │
└─────────────┘      └─────────────┘      └─────────────┘
```

### Pass to Background Tasks

```python
@shared_task(bind=True)
def process_asset(self, asset_id: int, correlation_id: str = None):
    logger.info(
        "Processing asset",
        asset_id=asset_id,
        correlation_id=correlation_id,
        task_id=self.request.id,
    )
```

### Use in Endpoints

```python
from app.middleware.logging import get_correlation_id

@router.post("/assets/upload")
async def upload(request: Request, ...):
    correlation_id = get_correlation_id(request)

    # Pass to background task
    process_asset.delay(
        asset_id=asset.id,
        correlation_id=correlation_id,
    )
```

---

## What to Log

### Do Log
- Request method, path, status code
- Duration/latency
- User ID (if authenticated)
- Correlation ID
- Error messages and types
- Important business events

### Don't Log
- Passwords or tokens
- Full request/response bodies
- Credit card numbers
- Personal information (GDPR)
- High-frequency debug info in production

```python
# Good
logger.info("User logged in", user_id=user.id)

# Bad - logging password!
logger.info("Login attempt", email=email, password=password)

# Bad - PII
logger.info("User updated", email=user.email, phone=user.phone)
```

---

## Log Levels

```python
logger.debug("Detailed debugging info")   # Development only
logger.info("Normal operations")           # Request completed
logger.warning("Something unexpected")     # Deprecation, retry
logger.error("Something failed")           # Caught exception
logger.critical("System is broken")        # Cannot continue
```

### When to Use Each

```python
# DEBUG - Development, verbose
logger.debug("Cache lookup", key=key, hit=True)

# INFO - Normal operations
logger.info("Asset uploaded", asset_id=123, size=1024)

# WARNING - Unusual but handled
logger.warning("Rate limit approaching", user_id=123, remaining=5)

# ERROR - Something failed
logger.error("Database query failed", error=str(e))

# CRITICAL - System-level failure
logger.critical("Cannot connect to database", error=str(e))
```

---

## Slow Request Detection

```python
class SlowRequestLoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, threshold_ms: float = 1000.0):
        super().__init__(app)
        self.threshold_ms = threshold_ms

    async def dispatch(self, request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        if duration_ms > self.threshold_ms:
            logger.warning(
                "Slow request detected",
                method=request.method,
                path=request.url.path,
                duration_ms=round(duration_ms, 2),
                threshold_ms=self.threshold_ms,
            )

        return response
```

---

## Client IP Detection

Handle proxies correctly:

```python
def get_client_ip(request: Request) -> str:
    # Check X-Forwarded-For (from proxy)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    # Check X-Real-IP
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Direct connection
    if request.client:
        return request.client.host

    return "unknown"
```

---

## Filtering Sensitive Data

```python
SENSITIVE_HEADERS = {"authorization", "x-api-key", "cookie"}
SENSITIVE_FIELDS = {"password", "token", "secret"}

def sanitize_headers(headers: dict) -> dict:
    return {
        k: "[REDACTED]" if k.lower() in SENSITIVE_HEADERS else v
        for k, v in headers.items()
    }

def sanitize_body(body: dict) -> dict:
    return {
        k: "[REDACTED]" if k.lower() in SENSITIVE_FIELDS else v
        for k, v in body.items()
    }
```

---

## Log Aggregation

Send logs to centralized systems:

### JSON to stdout (Docker/K8s)

```python
structlog.configure(
    processors=[
        ...,
        structlog.processors.JSONRenderer(),
    ],
)

# Docker/K8s collects stdout automatically
```

### Direct to Elasticsearch

```python
from elasticsearch import Elasticsearch

class ElasticsearchHandler(logging.Handler):
    def __init__(self, es_url, index):
        super().__init__()
        self.es = Elasticsearch(es_url)
        self.index = index

    def emit(self, record):
        self.es.index(
            index=self.index,
            document=record.__dict__,
        )
```

---

## Best Practices

### 1. Use Structured Logging

```python
# Bad
logger.info(f"User {user_id} uploaded file {filename}")

# Good
logger.info("File uploaded", user_id=user_id, filename=filename)
```

### 2. Include Context

```python
# Bad
logger.error("Failed")

# Good
logger.error(
    "Asset processing failed",
    asset_id=asset_id,
    error_type=type(e).__name__,
    error_message=str(e),
)
```

### 3. Log at Boundaries

```python
# Request entry
logger.info("Request started", ...)

# External service calls
logger.info("Calling external API", service="stripe")
logger.info("External API response", service="stripe", status=200)

# Request exit
logger.info("Request completed", ...)
```

### 4. Don't Log in Loops

```python
# Bad - floods logs
for item in items:
    logger.info("Processing item", item_id=item.id)

# Good - log summary
logger.info("Processing batch", count=len(items))
```

---

## Further Reading

- [Structlog Documentation](https://www.structlog.org/)
- [12-Factor App - Logs](https://12factor.net/logs)
- [OpenTelemetry](https://opentelemetry.io/)
