# Module 5: Rate Limiting, Caching & Monitoring

## Overview

This module adds production-readiness features to VisualVault: rate limiting to prevent abuse, caching for performance, and monitoring for observability. These are essential for running a reliable API at scale.

## Learning Objectives

By completing this module, you will be able to:

1. **Implement rate limiting** - Protect your API from abuse with SlowAPI
2. **Add Redis caching** - Speed up expensive operations
3. **Configure request logging** - Track requests with correlation IDs
4. **Collect metrics** - Monitor performance with Prometheus-compatible metrics
5. **Build health checks** - Comprehensive readiness probes
6. **Prepare for production** - Best practices for deployment

---

## Prerequisites

- Completed Module 4 (Background Processing)
- Docker containers running (`docker-compose up -d`)
- Redis available

---

## Lesson Plan

### Part 1: Rate Limiting (25 min)

**Concepts:**
- Why rate limiting matters
- Token bucket vs fixed window algorithms
- Per-user vs per-IP limits
- Tier-based limits for different user types

**Key Code:** `app/middleware/rate_limit.py`

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

def get_rate_limit_key(request: Request) -> str:
    """Identify requestor by API key, token, or IP."""
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return f"apikey:{api_key[:11]}"

    auth = request.headers.get("Authorization")
    if auth:
        return f"token:{auth[7:27]}"

    return get_remote_address(request)

limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=["60/minute"],
    storage_uri="redis://localhost:6379",
)
```

**Key Takeaway:** Rate limiting prevents abuse and ensures fair access. Use Redis as the backend for distributed rate limiting across multiple API instances.

**Read More:** [01-rate-limiting.md](./01-rate-limiting.md)

---

### Part 2: Redis Caching (25 min)

**Concepts:**
- When to cache (and when not to)
- Cache invalidation strategies
- TTL-based expiration
- Cache key design

**Key Code:** `app/services/cache.py`

```python
class CacheService:
    async def get(self, key: str) -> Any | None:
        value = await self.redis.get(key)
        return json.loads(value) if value else None

    async def set(self, key: str, value: Any, ttl: int = 300):
        await self.redis.setex(key, ttl, json.dumps(value))

    async def delete_pattern(self, pattern: str) -> int:
        keys = [k async for k in self.redis.scan_iter(match=pattern)]
        return await self.redis.delete(*keys) if keys else 0
```

**Key Takeaway:** Cache expensive operations but always plan for invalidation. When in doubt, use short TTLs.

**Read More:** [02-redis-caching.md](./02-redis-caching.md)

---

### Part 3: Request Logging (20 min)

**Concepts:**
- Structured logging with structlog
- Correlation IDs for request tracing
- Slow request detection
- What to log (and not log)

**Key Code:** `app/middleware/logging.py`

```python
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        correlation_id = str(uuid.uuid4())
        request.state.correlation_id = correlation_id

        start_time = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            "Request completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            correlation_id=correlation_id,
        )

        response.headers["X-Correlation-ID"] = correlation_id
        return response
```

**Key Takeaway:** Structured logging makes debugging easier. Correlation IDs let you trace requests across services.

**Read More:** [03-request-logging.md](./03-request-logging.md)

---

### Part 4: Metrics Collection (20 min)

**Concepts:**
- What metrics to collect
- Prometheus format
- Endpoint-level metrics
- Performance dashboards

**Key Code:** `app/middleware/metrics.py`

```python
class MetricsCollector:
    def record_request(self, method, path, status_code, latency_ms):
        key = f"{method}:{path}"
        self._endpoints[key].total_requests += 1
        self._endpoints[key].total_latency_ms += latency_ms
        if status_code >= 400:
            self._endpoints[key].total_errors += 1

    def get_prometheus_format(self) -> str:
        # Export metrics for Prometheus scraping
        ...
```

**Key Takeaway:** Metrics help you understand your API's behavior. Export in Prometheus format for easy integration with monitoring tools.

**Read More:** [04-metrics-monitoring.md](./04-metrics-monitoring.md)

---

### Part 5: Production Readiness (15 min)

**Concepts:**
- Health check patterns
- Graceful shutdown
- Configuration management
- Security hardening

**Read More:** [05-production-readiness.md](./05-production-readiness.md)

---

## Hands-On Exercises

### Exercise 1: Test Rate Limiting

```bash
# Send many requests quickly
for i in {1..100}; do
  curl -s http://localhost:8000/api/v1/health &
done
wait

# You should see 429 responses after hitting the limit
```

### Exercise 2: Check Cache Hit Rates

```bash
# First request - cache miss
time curl http://localhost:8000/api/v1/assets -H "Authorization: Bearer $TOKEN"

# Second request - cache hit (should be faster)
time curl http://localhost:8000/api/v1/assets -H "Authorization: Bearer $TOKEN"
```

### Exercise 3: View Metrics

```bash
# Get Prometheus metrics
curl http://localhost:8000/api/v1/health/metrics
```

### Exercise 4: Trace a Request

```bash
# Note the correlation ID in response headers
curl -v http://localhost:8000/api/v1/health 2>&1 | grep X-Correlation-ID

# Search logs for that correlation ID
docker-compose logs api | grep <correlation-id>
```

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `app/middleware/rate_limit.py` | Rate limiting with SlowAPI |
| `app/middleware/logging.py` | Request logging middleware |
| `app/middleware/metrics.py` | Metrics collection |
| `app/services/cache.py` | Redis caching service |
| `app/api/v1/health.py` | Health check endpoints |

---

## API Changes

### New Headers

| Header | Description |
|--------|-------------|
| `X-Correlation-ID` | Request tracing ID (response) |
| `X-Response-Time` | Request duration in ms |
| `X-RateLimit-Limit` | Maximum requests allowed |
| `X-RateLimit-Remaining` | Requests remaining |
| `Retry-After` | Seconds until rate limit resets (429 only) |

### New Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health/metrics` | Prometheus metrics |

---

## Common Issues & Solutions

### "Rate limit exceeded" errors in tests
**Cause:** Test client using same IP/key.
**Solution:** Use eager mode or increase limits in test config.

### Cache not working
**Cause:** Redis not connected or cache not initialized.
**Solution:** Check `REDIS_HOST` env var and `init_cache()` in lifespan.

### Metrics not showing
**Cause:** Metrics middleware not added.
**Solution:** Add `MetricsMiddleware` in `create_app()`.

### Slow health check
**Cause:** Worker health check waiting for timeout.
**Solution:** Reduce ping timeout or skip worker check.

---

## Performance Impact

| Feature | Overhead | Benefit |
|---------|----------|---------|
| Rate Limiting | ~1ms | Prevents abuse |
| Request Logging | ~0.5ms | Debugging capability |
| Metrics | ~0.1ms | Observability |
| Caching | Variable | 10-1000x speedup on hits |

---

## What's Next

Congratulations! You've completed all 5 modules of VisualVault:

1. **Module 1**: Project Setup & FastAPI Basics
2. **Module 2**: Database & Authentication
3. **Module 3**: File Uploads & Storage
4. **Module 4**: Background Processing & ML
5. **Module 5**: Rate Limiting, Caching & Monitoring

### Suggested Extensions

- Add WebSocket support for real-time processing updates
- Implement batch processing endpoints
- Add user quotas and billing
- Deploy to Kubernetes
- Set up CI/CD pipeline

---

## Additional Resources

- [SlowAPI Documentation](https://slowapi.readthedocs.io/)
- [Redis Commands](https://redis.io/commands/)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/naming/)
- [Structlog Documentation](https://www.structlog.org/)
