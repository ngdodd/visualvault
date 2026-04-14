# Rate Limiting: Protecting Your API

## Why Rate Limit?

Without rate limiting, a single user or bot could:

- **Overwhelm your servers** with thousands of requests
- **Cause denial of service** for other users
- **Rack up expensive bills** (ML inference, storage)
- **Scrape your entire database**
- **Brute force authentication**

---

## Rate Limiting Strategies

### Fixed Window

Count requests in fixed time windows:

```
Window: 1 minute
Limit: 60 requests

00:00:00 - 00:00:59 → 60 allowed
00:01:00 - 00:01:59 → 60 allowed (reset)
```

**Pros:** Simple, predictable
**Cons:** Burst at window boundaries (up to 120 at 00:00:59 - 00:01:01)

### Sliding Window

Smooth out the window boundaries:

```
At any point, look back 60 seconds
Count requests in that window
```

**Pros:** No boundary bursts
**Cons:** More memory/computation

### Token Bucket

Add tokens at a constant rate, spend on requests:

```
Bucket capacity: 60 tokens
Refill rate: 1 token/second
Request costs: 1 token

Allows bursts up to 60, then 1/second
```

**Pros:** Allows controlled bursts
**Cons:** More complex

---

## SlowAPI Setup

```python
# app/middleware/rate_limit.py

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["60/minute"],
    storage_uri="redis://localhost:6379/0",
    strategy="fixed-window",
)
```

### Configuration Options

```python
limiter = Limiter(
    key_func=get_rate_limit_key,    # How to identify requestors
    default_limits=["60/minute"],    # Default limit
    storage_uri="redis://...",       # Redis for distributed limiting
    strategy="fixed-window",         # or "moving-window"
    headers_enabled=True,            # Add rate limit headers
)
```

---

## Identifying Requestors

### By IP Address (Default)

```python
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
```

### By Authentication

```python
def get_rate_limit_key(request: Request) -> str:
    """Identify by API key, then JWT, then IP."""
    # Check API key first
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return f"apikey:{api_key[:11]}"

    # Check JWT token
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        # Use token prefix (user identity)
        return f"token:{auth[7:27]}"

    # Fall back to IP
    return f"ip:{get_remote_address(request)}"

limiter = Limiter(key_func=get_rate_limit_key, ...)
```

---

## Applying Limits

### Default Limit (All Endpoints)

```python
limiter = Limiter(default_limits=["60/minute"])
```

### Per-Endpoint Limits

```python
from slowapi import Limiter

limiter = Limiter(...)

@app.get("/upload")
@limiter.limit("10/minute")  # Override default
async def upload():
    pass

@app.post("/login")
@limiter.limit("5/minute")  # Strict for auth
async def login():
    pass
```

### Dynamic Limits

```python
def get_upload_limit(request: Request) -> str:
    """Different limits based on user tier."""
    user = get_current_user(request)
    if user.tier == "premium":
        return "100/minute"
    return "10/minute"

@app.post("/upload")
@limiter.limit(get_upload_limit)
async def upload():
    pass
```

---

## Tier-Based Limits

```python
RATE_LIMIT_TIERS = {
    "anonymous": "30/minute",
    "standard": "60/minute",
    "premium": "300/minute",
    "unlimited": "10000/minute",
}

def get_user_tier_limit(request: Request) -> str:
    """Get limit based on user's subscription tier."""
    api_key = request.headers.get("X-API-Key")
    if api_key:
        # Look up tier from API key
        tier = get_api_key_tier(api_key)
        return RATE_LIMIT_TIERS.get(tier, RATE_LIMIT_TIERS["standard"])

    return RATE_LIMIT_TIERS["anonymous"]
```

---

## FastAPI Integration

### Add to App

```python
# app/main.py

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.middleware.rate_limit import limiter

def create_app():
    app = FastAPI(...)

    # Attach limiter to app state
    app.state.limiter = limiter

    # Add exception handler
    app.add_exception_handler(
        RateLimitExceeded,
        rate_limit_exceeded_handler,
    )

    return app
```

### Custom Error Response

```python
from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

def rate_limit_exceeded_handler(
    request: Request,
    exc: RateLimitExceeded,
) -> JSONResponse:
    """Custom response for rate limit errors."""
    retry_after = getattr(exc, "retry_after", 60)

    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": f"Too many requests. Retry in {retry_after}s.",
            "retry_after": retry_after,
        },
        headers={
            "Retry-After": str(retry_after),
        },
    )
```

---

## Rate Limit Headers

Inform clients of their limit status:

```http
HTTP/1.1 200 OK
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1705320000
```

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 30
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 0
```

---

## Redis Backend

For multiple API instances, use Redis:

```python
limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=["60/minute"],
    storage_uri="redis://redis:6379/0",
)
```

**Why Redis?**
- Shared state across instances
- Fast atomic operations
- Automatic key expiration
- Cluster support for scale

---

## Testing Rate Limits

### Disable in Tests

```python
# conftest.py

@pytest.fixture
def app():
    from app.main import create_app
    app = create_app()
    # Disable rate limiting for tests
    app.state.limiter.enabled = False
    return app
```

### Test Rate Limit Behavior

```python
def test_rate_limit(client):
    # Enable limiter for this test
    client.app.state.limiter.enabled = True

    # Send requests until limited
    responses = []
    for _ in range(100):
        resp = client.get("/api/v1/health")
        responses.append(resp.status_code)

    # Should have some 429s
    assert 429 in responses
```

---

## Endpoint-Specific Limits

```python
ENDPOINT_LIMITS = {
    "/api/v1/auth/login": "5/minute",      # Prevent brute force
    "/api/v1/auth/register": "3/minute",   # Prevent spam
    "/api/v1/assets/upload": "10/minute",  # Expensive operation
    "/api/v1/search/image": "10/minute",   # ML inference
    "/api/v1/search/text": "30/minute",    # Less expensive
}
```

---

## Exemptions

### Skip for Internal Services

```python
def should_skip_rate_limit(request: Request) -> bool:
    """Skip rate limiting for internal services."""
    # Check for internal service header
    internal_token = request.headers.get("X-Internal-Token")
    if internal_token == settings.internal_service_token:
        return True

    # Skip for health checks
    if request.url.path.startswith("/api/v1/health"):
        return True

    return False

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if should_skip_rate_limit(request):
        return await call_next(request)
    # Apply rate limiting...
```

---

## Best Practices

### 1. Start Generous, Tighten Later

```python
# Start with loose limits
default_limits=["1000/minute"]

# Analyze usage patterns, then tighten
default_limits=["100/minute"]
```

### 2. Different Limits for Different Operations

```python
# Cheap operations
@limiter.limit("100/minute")
async def list_assets(): ...

# Expensive operations
@limiter.limit("10/minute")
async def process_image(): ...
```

### 3. Inform Users

```python
# Include limits in API documentation
# Return clear error messages
# Provide Retry-After header
```

### 4. Monitor and Alert

```python
# Track 429 response rates
# Alert if suddenly spiking (attack?)
# Alert if hitting limits unexpectedly (bug?)
```

### 5. Consider User Experience

```python
# Web users: higher limits, shorter windows
"100/minute"

# API users: consider burst needs
"60/minute;burst=20"
```

---

## Common Issues

### "Rate limit not working across instances"

```python
# Use Redis, not in-memory
storage_uri="redis://redis:6379/0"
```

### "Getting rate limited on health checks"

```python
# Exempt health check paths
if request.url.path.startswith("/health"):
    return await call_next(request)
```

### "Tests failing due to rate limits"

```python
# Disable in test environment
limiter = Limiter(
    ...
    enabled=settings.environment != "test",
)
```

---

## Further Reading

- [SlowAPI Documentation](https://slowapi.readthedocs.io/)
- [Token Bucket Algorithm](https://en.wikipedia.org/wiki/Token_bucket)
- [Rate Limiting Strategies](https://cloud.google.com/architecture/rate-limiting-strategies-techniques)
