# Redis Caching: Performance Optimization

## When to Cache

### Good Candidates
- Expensive database queries
- ML model predictions
- Computed aggregations
- External API responses
- User session data

### Bad Candidates
- Rapidly changing data
- User-specific sensitive data
- Data that must be real-time
- Very small/fast queries

---

## Cache Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────►│    API      │────►│   Redis     │
│             │     │             │     │   Cache     │
│             │◄────│             │◄────│             │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │                   │
                           │ Cache Miss        │
                           ▼                   │
                    ┌─────────────┐            │
                    │  Database   │────────────┘
                    │             │  Store in cache
                    └─────────────┘
```

---

## Our Cache Service

```python
# app/services/cache.py

import redis.asyncio as redis

class CacheService:
    def __init__(self, settings):
        self._redis: redis.Redis | None = None

    async def connect(self):
        self._redis = redis.from_url(
            self.settings.redis.url,
            encoding="utf-8",
            decode_responses=True,
        )

    async def get(self, key: str) -> Any | None:
        value = await self.redis.get(key)
        return json.loads(value) if value else None

    async def set(self, key: str, value: Any, ttl: int = 300):
        await self.redis.setex(key, ttl, json.dumps(value))

    async def delete(self, key: str):
        await self.redis.delete(key)

    async def delete_pattern(self, pattern: str) -> int:
        keys = [k async for k in self.redis.scan_iter(match=pattern)]
        return await self.redis.delete(*keys) if keys else 0
```

---

## Cache Key Design

### Naming Convention

```python
class CacheKeys:
    @staticmethod
    def user(user_id: int) -> str:
        return f"user:{user_id}"

    @staticmethod
    def user_assets(user_id: int) -> str:
        return f"user:{user_id}:assets"

    @staticmethod
    def asset_detail(asset_id: int) -> str:
        return f"asset:{asset_id}:detail"

    @staticmethod
    def search_results(user_id: int, query_hash: str) -> str:
        return f"search:{user_id}:{query_hash}"
```

### Key Patterns

```
user:123              # User profile
user:123:assets       # User's asset list
user:123:*            # All user data (for invalidation)
asset:456             # Asset data
asset:456:detail      # Asset with ML features
search:123:abc123     # Search results
```

---

## TTL Strategies

```python
class CacheTTL:
    SHORT = 60       # 1 minute - frequently changing
    MEDIUM = 300     # 5 minutes - moderate updates
    LONG = 3600      # 1 hour - stable data
    DAY = 86400      # 24 hours - very stable

    # Domain-specific
    USER_DATA = MEDIUM
    ASSET_LIST = SHORT      # Changes on upload
    ASSET_DETAIL = MEDIUM   # Changes on processing
    SEARCH_RESULTS = SHORT  # Relevance may change
    EMBEDDINGS = LONG       # Rarely change
```

---

## Caching Decorator

```python
def cached(key_builder, ttl=300):
    """Decorator for caching function results."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = get_cache_service()
            key = key_builder(*args, **kwargs)

            # Try cache first
            cached_value = await cache.get(key)
            if cached_value is not None:
                return cached_value

            # Call function
            result = await func(*args, **kwargs)

            # Store in cache
            if result is not None:
                await cache.set(key, result, ttl=ttl)

            return result
        return wrapper
    return decorator

# Usage
@cached(
    key_builder=lambda user_id: f"user:{user_id}:profile",
    ttl=300,
)
async def get_user_profile(user_id: int):
    return await db.get(User, user_id)
```

---

## Cache Invalidation

> "There are only two hard things in Computer Science: cache invalidation and naming things."

### On Update

```python
async def update_asset(asset_id: int, data: dict):
    # Update database
    await db.update(Asset, asset_id, data)

    # Invalidate cache
    cache = get_cache_service()
    await cache.delete(f"asset:{asset_id}")
    await cache.delete(f"asset:{asset_id}:detail")
```

### Pattern Invalidation

```python
async def delete_user(user_id: int):
    # Delete from database
    await db.delete(User, user_id)

    # Invalidate ALL user's cached data
    cache = get_cache_service()
    await cache.delete_pattern(f"user:{user_id}:*")
```

### Invalidation Decorator

```python
def invalidate_on_change(key_patterns):
    """Invalidate cache after function runs."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)

            cache = get_cache_service()
            for pattern_builder in key_patterns:
                pattern = pattern_builder(*args, **kwargs)
                await cache.delete_pattern(pattern)

            return result
        return wrapper
    return decorator

# Usage
@invalidate_on_change([
    lambda user_id, data: f"user:{user_id}:*",
])
async def update_user(user_id: int, data: dict):
    ...
```

---

## Caching Patterns

### Cache-Aside (Lazy Loading)

```python
async def get_asset(asset_id: int):
    cache = get_cache_service()
    key = f"asset:{asset_id}"

    # 1. Check cache
    cached = await cache.get(key)
    if cached:
        return cached

    # 2. Load from database
    asset = await db.get(Asset, asset_id)

    # 3. Store in cache
    await cache.set(key, asset.to_dict(), ttl=300)

    return asset
```

### Write-Through

```python
async def create_asset(data: dict):
    # 1. Write to database
    asset = await db.create(Asset, data)

    # 2. Write to cache immediately
    cache = get_cache_service()
    await cache.set(f"asset:{asset.id}", asset.to_dict(), ttl=300)

    return asset
```

### Cache Warming

```python
async def warm_cache():
    """Pre-populate cache on startup."""
    cache = get_cache_service()

    # Load frequently accessed data
    popular_assets = await db.get_popular_assets(limit=100)
    for asset in popular_assets:
        await cache.set(
            f"asset:{asset.id}",
            asset.to_dict(),
            ttl=CacheTTL.LONG,
        )
```

---

## Practical Examples

### Cache Asset List

```python
async def get_user_assets(user_id: int, page: int = 1):
    cache = get_cache_service()
    key = f"user:{user_id}:assets:page:{page}"

    # Check cache
    cached = await cache.get(key)
    if cached:
        return cached

    # Query database
    assets = await db.query(Asset).where(
        Asset.user_id == user_id
    ).paginate(page).all()

    # Convert to dict for JSON serialization
    result = [a.to_dict() for a in assets]

    # Cache for 1 minute (changes on upload)
    await cache.set(key, result, ttl=60)

    return result
```

### Cache Search Results

```python
import hashlib

async def search_by_text(user_id: int, query: str):
    cache = get_cache_service()

    # Hash query for cache key
    query_hash = hashlib.md5(query.encode()).hexdigest()[:8]
    key = f"search:{user_id}:{query_hash}"

    # Check cache
    cached = await cache.get(key)
    if cached:
        return cached

    # Perform expensive search
    results = await perform_similarity_search(user_id, query)

    # Cache for 5 minutes
    await cache.set(key, results, ttl=300)

    return results
```

---

## Monitoring Cache

### Hit Rate

```python
class CacheService:
    def __init__(self):
        self.hits = 0
        self.misses = 0

    async def get(self, key: str):
        value = await self.redis.get(key)
        if value:
            self.hits += 1
        else:
            self.misses += 1
        return json.loads(value) if value else None

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0
```

### Redis INFO

```python
async def get_cache_stats():
    info = await cache.redis.info("stats")
    return {
        "hits": info["keyspace_hits"],
        "misses": info["keyspace_misses"],
        "hit_rate": info["keyspace_hits"] / (
            info["keyspace_hits"] + info["keyspace_misses"]
        ),
    }
```

---

## Best Practices

### 1. Always Set TTL

```python
# Good - expires in 5 minutes
await cache.set(key, value, ttl=300)

# Bad - never expires, memory leak
await cache.set(key, value)
```

### 2. Handle Cache Failures Gracefully

```python
async def get_with_fallback(key: str, fallback):
    try:
        cached = await cache.get(key)
        if cached:
            return cached
    except Exception as e:
        logger.warning(f"Cache error: {e}")

    # Fall back to database
    return await fallback()
```

### 3. Don't Cache Errors

```python
async def get_asset(asset_id: int):
    cached = await cache.get(key)
    if cached:
        return cached

    asset = await db.get(Asset, asset_id)

    # Only cache successful results
    if asset:
        await cache.set(key, asset.to_dict(), ttl=300)

    return asset
```

### 4. Use Appropriate TTLs

```python
# Too short - no benefit
ttl=1

# Too long - stale data
ttl=86400

# Just right - balance freshness and performance
ttl=300
```

---

## Further Reading

- [Redis Commands](https://redis.io/commands/)
- [Caching Strategies](https://aws.amazon.com/caching/best-practices/)
- [Cache Invalidation Patterns](https://www.prisma.io/dataguide/managing-databases/introduction-database-caching)
