# Production Readiness: Deploying with Confidence

## Production Checklist

Before deploying to production, ensure:

- [ ] All secrets in environment variables (not in code)
- [ ] Debug mode disabled
- [ ] Docs endpoints disabled or protected
- [ ] Rate limiting enabled with Redis backend
- [ ] Health checks configured
- [ ] Structured logging enabled
- [ ] Metrics collection active
- [ ] Database connection pooling configured
- [ ] CORS properly restricted
- [ ] SSL/TLS enabled

---

## Health Check Patterns

### Liveness Probe

"Is the process alive?"

```python
@router.get("/health/live")
async def liveness():
    """
    Kubernetes liveness probe.

    Returns 200 if the process is running.
    If this fails, Kubernetes will restart the pod.
    """
    return {"status": "alive"}
```

### Readiness Probe

"Can the process handle requests?"

```python
@router.get("/health/ready")
async def readiness(db: DbSessionDep):
    """
    Kubernetes readiness probe.

    Returns 200 if all dependencies are healthy.
    If this fails, Kubernetes removes from load balancer.
    """
    checks = await run_health_checks(db)

    all_healthy = all(
        c.status == HealthStatus.HEALTHY
        for c in checks.values()
    )

    status_code = 200 if all_healthy else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ready" if all_healthy else "not_ready", "checks": checks}
    )
```

### Startup Probe

"Has the process finished initializing?"

```python
@router.get("/health/startup")
async def startup():
    """
    Kubernetes startup probe.

    Returns 200 once initialization is complete.
    Prevents liveness checks during slow startups (ML model loading).
    """
    if not app_initialized:
        raise HTTPException(503, "Still initializing")
    return {"status": "started"}
```

---

## Comprehensive Health Check

```python
# app/api/v1/health.py

from enum import Enum
from dataclasses import dataclass
import time

class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

@dataclass
class ComponentHealth:
    status: HealthStatus
    latency_ms: float | None = None
    message: str | None = None

async def check_database_health(db) -> ComponentHealth:
    """Check database connectivity."""
    try:
        start = time.perf_counter()
        await db.execute(text("SELECT 1"))
        latency = (time.perf_counter() - start) * 1000
        return ComponentHealth(
            status=HealthStatus.HEALTHY,
            latency_ms=round(latency, 2),
        )
    except Exception as e:
        return ComponentHealth(
            status=HealthStatus.UNHEALTHY,
            message=str(e),
        )

async def check_redis_health() -> ComponentHealth:
    """Check Redis connectivity."""
    try:
        cache = get_cache_service()
        if not cache or not cache.redis:
            return ComponentHealth(
                status=HealthStatus.UNHEALTHY,
                message="Cache not initialized",
            )

        start = time.perf_counter()
        await cache.redis.ping()
        latency = (time.perf_counter() - start) * 1000
        return ComponentHealth(
            status=HealthStatus.HEALTHY,
            latency_ms=round(latency, 2),
        )
    except Exception as e:
        return ComponentHealth(
            status=HealthStatus.UNHEALTHY,
            message=str(e),
        )

async def check_storage_health() -> ComponentHealth:
    """Check storage accessibility."""
    try:
        storage = get_storage_service()
        settings = get_settings()

        # Check if directories exist and are writable
        if not settings.storage.uploads_path.exists():
            return ComponentHealth(
                status=HealthStatus.UNHEALTHY,
                message="Upload directory does not exist",
            )

        return ComponentHealth(status=HealthStatus.HEALTHY)
    except Exception as e:
        return ComponentHealth(
            status=HealthStatus.UNHEALTHY,
            message=str(e),
        )

async def check_worker_health() -> ComponentHealth:
    """Check Celery worker availability."""
    try:
        from app.workers.celery_app import celery_app

        # Ping workers with short timeout
        inspector = celery_app.control.inspect(timeout=1.0)
        active = inspector.active()

        if not active:
            return ComponentHealth(
                status=HealthStatus.DEGRADED,
                message="No active workers",
            )

        worker_count = len(active)
        return ComponentHealth(
            status=HealthStatus.HEALTHY,
            message=f"{worker_count} workers active",
        )
    except Exception as e:
        return ComponentHealth(
            status=HealthStatus.DEGRADED,
            message=f"Cannot reach workers: {e}",
        )
```

---

## Graceful Shutdown

```python
# app/main.py

import signal
import asyncio

shutdown_event = asyncio.Event()

def handle_shutdown(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info("Shutdown signal received", signal=signum)
    shutdown_event.set()

# Register signal handlers
signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting application")
    await init_services()

    yield

    # Shutdown
    logger.info("Shutting down gracefully")

    # Give in-flight requests time to complete
    await asyncio.sleep(5)

    # Close connections
    await close_cache()
    await close_db()

    logger.info("Shutdown complete")
```

---

## Configuration Management

### Environment-Based Settings

```python
# app/config.py

from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # Application
    app_name: str = "VisualVault"
    environment: str = "development"
    debug: bool = False

    # Security
    secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Database
    database_url: str
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Rate Limiting
    rate_limit_default: str = "60/minute"
    rate_limit_enabled: bool = True

    model_config = ConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        case_sensitive=False,
    )

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### Environment Files

```bash
# .env.development
DEBUG=true
DATABASE_URL=postgresql://user:pass@localhost:5432/visualvault_dev
SECRET_KEY=dev-secret-key-not-for-production

# .env.production
DEBUG=false
DATABASE_URL=postgresql://user:pass@db-host:5432/visualvault
SECRET_KEY=${GENERATED_SECRET}  # Set via secrets manager
```

### Secret Management

```python
# Never commit secrets to code!

# Bad
SECRET_KEY = "my-secret-key-123"

# Good - from environment
SECRET_KEY = os.environ["SECRET_KEY"]

# Better - from secrets manager
import boto3
def get_secret(secret_name: str) -> str:
    client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId=secret_name)
    return response["SecretString"]
```

---

## Security Hardening

### Disable Debug in Production

```python
app = FastAPI(
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
)
```

### Restrict CORS

```python
# Development
cors_origins = ["*"]

# Production
cors_origins = [
    "https://app.visualvault.com",
    "https://admin.visualvault.com",
]
```

### Security Headers

```python
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
        response.headers["Content-Security-Policy"] = "default-src 'self'"

        return response
```

### Input Validation

```python
from pydantic import BaseModel, field_validator
import re

class UserCreate(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", v):
            raise ValueError("Invalid email format")
        return v.lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain uppercase letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain number")
        return v
```

---

## Database Connection Pooling

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.pool import QueuePool

engine = create_async_engine(
    settings.database_url,
    poolclass=QueuePool,
    pool_size=5,          # Steady-state connections
    max_overflow=10,      # Extra connections when busy
    pool_timeout=30,      # Wait time for connection
    pool_recycle=1800,    # Recycle connections every 30 min
    pool_pre_ping=True,   # Verify connection before use
)
```

---

## Kubernetes Deployment

### Deployment Manifest

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: visualvault-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: visualvault-api
  template:
    metadata:
      labels:
        app: visualvault-api
    spec:
      containers:
        - name: api
          image: visualvault:latest
          ports:
            - containerPort: 8000
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: visualvault-secrets
                  key: database-url
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "500m"
          livenessProbe:
            httpGet:
              path: /api/v1/health/live
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /api/v1/health/ready
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 5
          startupProbe:
            httpGet:
              path: /api/v1/health/startup
              port: 8000
            failureThreshold: 30
            periodSeconds: 10
```

### Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: visualvault-api
spec:
  selector:
    app: visualvault-api
  ports:
    - port: 80
      targetPort: 8000
  type: ClusterIP
```

### Ingress

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: visualvault-ingress
  annotations:
    nginx.ingress.kubernetes.io/rate-limit: "100"
spec:
  rules:
    - host: api.visualvault.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: visualvault-api
                port:
                  number: 80
```

---

## Docker Production Build

```dockerfile
# Dockerfile.prod
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    libpq5 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application
COPY app/ app/

# Create non-root user
RUN useradd --create-home appuser
USER appuser

# Run with production server
CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000"]
```

---

## Production Logging

```python
import logging
import structlog

def configure_logging(environment: str):
    """Configure logging for production."""

    # Set log level based on environment
    log_level = logging.DEBUG if environment == "development" else logging.INFO

    # Configure structlog
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if environment == "production":
        # JSON for log aggregation
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Pretty print for development
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        level=log_level,
    )
```

---

## Error Handling

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import traceback

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions."""

    # Log full traceback
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        traceback=traceback.format_exc(),
    )

    # Return safe error message (no internal details)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "An unexpected error occurred",
        },
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with logging."""

    logger.warning(
        "HTTP exception",
        path=request.url.path,
        status_code=exc.status_code,
        detail=exc.detail,
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
        },
    )
```

---

## Deployment Checklist

### Pre-Deploy
- [ ] Run all tests
- [ ] Check for security vulnerabilities (`pip audit`)
- [ ] Review environment configuration
- [ ] Database migrations prepared
- [ ] Rollback plan documented

### Deploy
- [ ] Database migrations applied
- [ ] Deploy new version
- [ ] Verify health checks pass
- [ ] Monitor error rates
- [ ] Check key metrics

### Post-Deploy
- [ ] Verify functionality with smoke tests
- [ ] Monitor for 30 minutes
- [ ] Update runbook if needed
- [ ] Communicate deployment completion

---

## Further Reading

- [12-Factor App](https://12factor.net/)
- [Kubernetes Best Practices](https://kubernetes.io/docs/concepts/configuration/overview/)
- [FastAPI in Production](https://fastapi.tiangolo.com/deployment/)
- [OWASP Security Guidelines](https://owasp.org/www-project-web-security-testing-guide/)
