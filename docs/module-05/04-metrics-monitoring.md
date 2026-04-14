# Metrics & Monitoring: Observability at Scale

## Why Collect Metrics?

Metrics answer critical questions:

- **How is my API performing?** (latency, throughput)
- **Where are the bottlenecks?** (slow endpoints)
- **Is something broken?** (error rates)
- **Do I need to scale?** (resource usage)

---

## Types of Metrics

### Counter
Monotonically increasing value:
```
Total requests: 1000, 1001, 1002, ...
Total errors: 50, 51, 52, ...
```

### Gauge
Point-in-time value that can go up or down:
```
Active connections: 5, 8, 3, 10, ...
Memory usage: 512MB, 480MB, 520MB, ...
```

### Histogram
Distribution of values:
```
Request latency buckets:
  <10ms: 500 requests
  <50ms: 300 requests
  <100ms: 150 requests
  <500ms: 50 requests
```

---

## Our Metrics Collector

```python
# app/middleware/metrics.py

from dataclasses import dataclass, field
from collections import defaultdict
import time

@dataclass
class EndpointMetrics:
    total_requests: int = 0
    total_errors: int = 0
    total_latency_ms: float = 0.0
    latency_buckets: dict = field(default_factory=lambda: {
        10: 0, 50: 0, 100: 0, 500: 0, 1000: 0, 5000: 0
    })

class MetricsCollector:
    def __init__(self):
        self._endpoints: dict[str, EndpointMetrics] = defaultdict(EndpointMetrics)
        self._start_time = time.time()

    def record_request(
        self,
        method: str,
        path: str,
        status_code: int,
        latency_ms: float,
    ):
        key = f"{method}:{self._normalize_path(path)}"
        metrics = self._endpoints[key]

        metrics.total_requests += 1
        metrics.total_latency_ms += latency_ms

        if status_code >= 400:
            metrics.total_errors += 1

        # Record in latency buckets
        for bucket in sorted(metrics.latency_buckets.keys()):
            if latency_ms <= bucket:
                metrics.latency_buckets[bucket] += 1
                break

    def _normalize_path(self, path: str) -> str:
        """Replace IDs with placeholders for grouping."""
        import re
        # /assets/123 -> /assets/{id}
        return re.sub(r'/\d+', '/{id}', path)
```

---

## Prometheus Format

Industry standard for metrics:

```python
def get_prometheus_format(self) -> str:
    lines = []

    # Uptime
    uptime = time.time() - self._start_time
    lines.append(f"# HELP api_uptime_seconds API uptime")
    lines.append(f"# TYPE api_uptime_seconds gauge")
    lines.append(f"api_uptime_seconds {uptime:.2f}")

    # Request metrics per endpoint
    lines.append(f"# HELP api_requests_total Total requests")
    lines.append(f"# TYPE api_requests_total counter")

    for key, metrics in self._endpoints.items():
        method, path = key.split(":", 1)
        labels = f'method="{method}",path="{path}"'

        lines.append(f"api_requests_total{{{labels}}} {metrics.total_requests}")

    # Error metrics
    lines.append(f"# HELP api_errors_total Total errors")
    lines.append(f"# TYPE api_errors_total counter")

    for key, metrics in self._endpoints.items():
        method, path = key.split(":", 1)
        labels = f'method="{method}",path="{path}"'

        lines.append(f"api_errors_total{{{labels}}} {metrics.total_errors}")

    # Latency histograms
    lines.append(f"# HELP api_latency_ms_bucket Request latency")
    lines.append(f"# TYPE api_latency_ms_bucket histogram")

    for key, metrics in self._endpoints.items():
        method, path = key.split(":", 1)

        for bucket, count in sorted(metrics.latency_buckets.items()):
            labels = f'method="{method}",path="{path}",le="{bucket}"'
            lines.append(f"api_latency_ms_bucket{{{labels}}} {count}")

    return "\n".join(lines)
```

### Example Output

```
# HELP api_uptime_seconds API uptime
# TYPE api_uptime_seconds gauge
api_uptime_seconds 3600.00

# HELP api_requests_total Total requests
# TYPE api_requests_total counter
api_requests_total{method="GET",path="/api/v1/assets"} 1500
api_requests_total{method="POST",path="/api/v1/assets/upload"} 200

# HELP api_errors_total Total errors
# TYPE api_errors_total counter
api_errors_total{method="GET",path="/api/v1/assets"} 5
api_errors_total{method="POST",path="/api/v1/assets/upload"} 12

# HELP api_latency_ms_bucket Request latency
# TYPE api_latency_ms_bucket histogram
api_latency_ms_bucket{method="GET",path="/api/v1/assets",le="10"} 800
api_latency_ms_bucket{method="GET",path="/api/v1/assets",le="50"} 500
api_latency_ms_bucket{method="GET",path="/api/v1/assets",le="100"} 150
```

---

## Metrics Middleware

```python
# app/middleware/metrics.py

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import time

# Global collector instance
_metrics_collector: MetricsCollector | None = None

def get_metrics_collector() -> MetricsCollector:
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector

class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip metrics endpoint to avoid recursion
        if request.url.path.endswith("/metrics"):
            return await call_next(request)

        start_time = time.perf_counter()
        response = await call_next(request)
        latency_ms = (time.perf_counter() - start_time) * 1000

        # Record metrics
        collector = get_metrics_collector()
        collector.record_request(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            latency_ms=latency_ms,
        )

        return response
```

---

## Metrics Endpoint

```python
# app/api/v1/health.py

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from app.middleware.metrics import get_metrics_collector

router = APIRouter(prefix="/health", tags=["Health"])

@router.get("/metrics", response_class=PlainTextResponse)
async def get_metrics() -> str:
    """
    Prometheus-compatible metrics endpoint.

    Scrape this endpoint with Prometheus to collect metrics.
    """
    collector = get_metrics_collector()
    return collector.get_prometheus_format()
```

---

## Key Metrics to Track

### API Health
```python
# Request rate
api_requests_total

# Error rate
api_errors_total / api_requests_total

# Latency percentiles
api_latency_ms_bucket (p50, p95, p99)
```

### Business Metrics
```python
# Assets uploaded
assets_uploaded_total

# ML processing time
ml_processing_duration_seconds

# Search queries
search_queries_total
```

### Infrastructure
```python
# Database connections
db_connections_active

# Redis memory
redis_memory_used_bytes

# Celery queue depth
celery_queue_length
```

---

## Alerting Thresholds

### Critical (Page immediately)
```yaml
- Error rate > 5%
- Latency p99 > 5s
- Database connections exhausted
- Worker queue depth > 1000
```

### Warning (Investigate soon)
```yaml
- Error rate > 1%
- Latency p95 > 1s
- Cache hit rate < 50%
- Disk usage > 80%
```

### Info (Review periodically)
```yaml
- Traffic patterns
- Endpoint usage distribution
- User growth trends
```

---

## Prometheus Integration

### prometheus.yml

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'visualvault'
    static_configs:
      - targets: ['api:8000']
    metrics_path: '/api/v1/health/metrics'
```

### Docker Compose Addition

```yaml
services:
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

---

## Grafana Dashboard

### Request Rate Panel

```
Query: rate(api_requests_total[5m])
Title: "Requests per Second"
Type: Time series
```

### Error Rate Panel

```
Query: rate(api_errors_total[5m]) / rate(api_requests_total[5m]) * 100
Title: "Error Rate %"
Type: Gauge
Thresholds: 1% (yellow), 5% (red)
```

### Latency Panel

```
Query: histogram_quantile(0.95, rate(api_latency_ms_bucket[5m]))
Title: "P95 Latency"
Type: Time series
```

---

## Custom Business Metrics

```python
class BusinessMetrics:
    def __init__(self):
        self.assets_uploaded = 0
        self.assets_processed = 0
        self.searches_performed = 0
        self.embedding_time_total = 0.0

    def record_upload(self, file_size: int):
        self.assets_uploaded += 1

    def record_processing(self, duration_ms: float):
        self.assets_processed += 1
        self.embedding_time_total += duration_ms

    def record_search(self, query_type: str, results_count: int):
        self.searches_performed += 1

    def get_prometheus_format(self) -> str:
        return f"""
# HELP business_assets_uploaded_total Total assets uploaded
# TYPE business_assets_uploaded_total counter
business_assets_uploaded_total {self.assets_uploaded}

# HELP business_assets_processed_total Total assets processed by ML
# TYPE business_assets_processed_total counter
business_assets_processed_total {self.assets_processed}

# HELP business_searches_total Total search queries
# TYPE business_searches_total counter
business_searches_total {self.searches_performed}
"""
```

---

## Best Practices

### 1. Normalize Paths

```python
# Bad - creates infinite unique keys
"/assets/123", "/assets/456", "/assets/789"

# Good - group by pattern
"/assets/{id}"
```

### 2. Use Labels Wisely

```python
# Bad - high cardinality
labels = f'user_id="{user.id}"'  # Millions of unique values

# Good - bounded cardinality
labels = f'user_tier="{user.tier}"'  # Few unique values
```

### 3. Avoid Expensive Computations

```python
# Bad - computes on every request
def expensive_metric():
    return sum(heavy_computation() for _ in range(1000))

# Good - cache or pre-compute
@cached(ttl=60)
def expensive_metric():
    return sum(heavy_computation() for _ in range(1000))
```

### 4. Include Units in Names

```python
# Bad
latency = 150

# Good
latency_ms = 150
latency_seconds = 0.15
```

---

## Debugging with Metrics

### Find Slow Endpoints

```
# Top 5 slowest endpoints by p95 latency
sort_desc(histogram_quantile(0.95, rate(api_latency_ms_bucket[5m])))
```

### Find Error Sources

```
# Endpoints with highest error rates
topk(5, rate(api_errors_total[1h]) / rate(api_requests_total[1h]))
```

### Capacity Planning

```
# Current request rate vs. historical
rate(api_requests_total[5m]) vs. rate(api_requests_total[5m] offset 7d)
```

---

## Further Reading

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Dashboards](https://grafana.com/grafana/dashboards/)
- [RED Method](https://www.weave.works/blog/the-red-method-key-metrics-for-microservices-architecture/)
- [USE Method](https://www.brendangregg.com/usemethod.html)
