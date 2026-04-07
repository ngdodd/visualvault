# Understanding FastAPI

## What is FastAPI?

FastAPI is a modern Python web framework for building APIs. It's designed to be:

- **Fast**: One of the fastest Python frameworks (on par with Node.js and Go)
- **Easy**: Intuitive design, great editor support, minimal boilerplate
- **Robust**: Automatic validation, serialization, and documentation

**Why FastAPI for ML?**
- Async support for handling concurrent requests
- Built-in request validation (critical for ML inputs)
- Automatic API documentation (great for model endpoints)
- Easy integration with PyTorch, TensorFlow, etc.

---

## Core Concepts

### 1. The Application Instance

```python
from fastapi import FastAPI

app = FastAPI(
    title="VisualVault",
    description="Visual Asset Intelligence API",
    version="0.1.0",
)
```

This creates your application. The `app` object is:
- An ASGI application (Asynchronous Server Gateway Interface)
- The central registry for all your routes, middleware, and configuration
- What you pass to the server (uvicorn)

---

### 2. Routes and Endpoints

```python
@app.get("/")
def read_root():
    return {"message": "Hello World"}

@app.get("/items/{item_id}")
def read_item(item_id: int, q: str = None):
    return {"item_id": item_id, "q": q}
```

**Decorators** (`@app.get`, `@app.post`, etc.) register functions as endpoints.

| Decorator | HTTP Method | Typical Use |
|-----------|-------------|-------------|
| `@app.get()` | GET | Read/retrieve data |
| `@app.post()` | POST | Create data |
| `@app.put()` | PUT | Update (replace) data |
| `@app.patch()` | PATCH | Update (partial) data |
| `@app.delete()` | DELETE | Delete data |

---

### 3. Path Parameters

```python
@app.get("/users/{user_id}")
def get_user(user_id: int):
    return {"user_id": user_id}
```

- `{user_id}` in the path becomes a function parameter
- Type hints (`user_id: int`) provide automatic validation
- If someone requests `/users/abc`, FastAPI returns a 422 error automatically

---

### 4. Query Parameters

```python
@app.get("/items")
def list_items(skip: int = 0, limit: int = 10):
    return {"skip": skip, "limit": limit}
```

Parameters not in the path become query parameters:
- `/items` → `{"skip": 0, "limit": 10}` (defaults)
- `/items?skip=20&limit=50` → `{"skip": 20, "limit": 50}`

---

### 5. Request Bodies (Pydantic Models)

```python
from pydantic import BaseModel

class Item(BaseModel):
    name: str
    price: float
    description: str | None = None

@app.post("/items")
def create_item(item: Item):
    return {"name": item.name, "price": item.price}
```

**What happens:**
1. Client sends JSON: `{"name": "Widget", "price": 9.99}`
2. FastAPI validates it matches the `Item` schema
3. If valid, creates an `Item` instance
4. If invalid, returns 422 error with details

---

### 6. Response Models

```python
class ItemResponse(BaseModel):
    id: int
    name: str
    price: float

@app.get("/items/{item_id}", response_model=ItemResponse)
def get_item(item_id: int):
    # Even if we return extra fields, only id, name, price are sent
    return {"id": item_id, "name": "Widget", "price": 9.99, "secret": "hidden"}
```

`response_model` ensures:
- Response matches the schema
- Extra fields are filtered out (security!)
- Documentation shows the expected response

---

## Our Application Structure

### The Application Factory Pattern

```python
# app/main.py

def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory function."""
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )

    app.include_router(api_router, prefix="/api/v1")
    return app

# Create the default instance
app = create_app()
```

**Why use a factory?**

1. **Testing**: Create apps with different configurations
   ```python
   def test_something():
       test_settings = Settings(debug=True, database=test_db)
       app = create_app(test_settings)
   ```

2. **Flexibility**: Multiple app instances if needed

3. **Clean separation**: Configuration separate from initialization

---

### Lifespan Events

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # === STARTUP ===
    # Runs once when application starts
    logger.info("Starting application")

    # Initialize resources
    # - Database connection pools
    # - Load ML models
    # - Warm caches

    yield  # Application runs here

    # === SHUTDOWN ===
    # Runs once when application stops
    logger.info("Shutting down")

    # Cleanup resources
    # - Close database connections
    # - Save state if needed
```

**The `yield` statement:**
- Everything before `yield` runs at startup
- Everything after `yield` runs at shutdown
- The app handles requests between startup and shutdown

**Old way (deprecated):**
```python
@app.on_event("startup")
async def startup():
    ...

@app.on_event("shutdown")
async def shutdown():
    ...
```

The lifespan context manager is the modern replacement.

---

### Routers

Instead of putting all endpoints in `main.py`, we organize them into routers:

```python
# app/api/v1/health.py
from fastapi import APIRouter

router = APIRouter()

@router.get("")
async def health_check():
    return {"status": "healthy"}

@router.get("/ready")
async def readiness_check():
    return {"status": "ready", "components": {...}}
```

```python
# app/api/v1/router.py
from fastapi import APIRouter
from app.api.v1 import health, assets, search

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(assets.router, prefix="/assets", tags=["Assets"])
api_router.include_router(search.router, prefix="/search", tags=["Search"])
```

```python
# app/main.py
app.include_router(api_router, prefix="/api/v1")
```

**Result:**
- `/api/v1/health` → health check
- `/api/v1/health/ready` → readiness check
- `/api/v1/assets` → asset endpoints
- `/api/v1/search` → search endpoints

**Benefits:**
- Organized code (one file per feature)
- Reusable routers
- Clear URL structure
- Better documentation grouping (via `tags`)

---

## Dependency Injection

One of FastAPI's most powerful features.

### Basic Dependency

```python
from fastapi import Depends

def get_settings():
    return Settings()

@app.get("/info")
def get_info(settings: Settings = Depends(get_settings)):
    return {"app_name": settings.app_name}
```

**What happens:**
1. FastAPI sees `Depends(get_settings)`
2. Calls `get_settings()` before your endpoint
3. Passes the result as the `settings` parameter

### Why Use Dependencies?

1. **Reusability**: Same logic across many endpoints
2. **Testability**: Easy to mock/override
3. **Separation**: Keep endpoints focused
4. **Composition**: Dependencies can have dependencies

### The Annotated Pattern (Recommended)

```python
from typing import Annotated
from fastapi import Depends

# Define once
SettingsDep = Annotated[Settings, Depends(get_settings)]

# Use anywhere
@app.get("/info")
def get_info(settings: SettingsDep):
    return {"app_name": settings.app_name}

@app.get("/debug")
def get_debug(settings: SettingsDep):
    return {"debug": settings.debug}
```

Cleaner than repeating `Depends(...)` everywhere.

### Common Dependencies

```python
# Database session
async def get_db():
    async with async_session() as session:
        yield session

DbSession = Annotated[AsyncSession, Depends(get_db)]

# Current authenticated user
async def get_current_user(token: str = Depends(oauth2_scheme)):
    user = await verify_token(token)
    return user

CurrentUser = Annotated[User, Depends(get_current_user)]

# Pagination parameters
def get_pagination(page: int = 1, size: int = 20):
    return {"page": page, "size": size}

Pagination = Annotated[dict, Depends(get_pagination)]
```

### Using in Endpoints

```python
@app.get("/items")
async def list_items(
    db: DbSession,
    user: CurrentUser,
    pagination: Pagination,
):
    items = await db.query(Item).filter(Item.user_id == user.id).all()
    return items
```

FastAPI automatically:
- Creates a database session
- Validates the auth token and gets the user
- Parses pagination from query params
- Passes all three to your function

---

## Async vs Sync

FastAPI supports both:

```python
# Synchronous (blocking)
@app.get("/sync")
def sync_endpoint():
    result = slow_database_query()  # Blocks the worker
    return result

# Asynchronous (non-blocking)
@app.get("/async")
async def async_endpoint():
    result = await async_database_query()  # Doesn't block
    return result
```

**When to use async:**
- Database queries (with async driver)
- HTTP requests to external services
- File I/O
- Anything that waits

**When sync is fine:**
- CPU-bound ML inference
- Simple computations
- Legacy synchronous libraries

**Important:** Don't mix! Don't call synchronous blocking code inside an async function without using `run_in_executor`.

---

## Error Handling

### Raising HTTP Exceptions

```python
from fastapi import HTTPException

@app.get("/items/{item_id}")
async def get_item(item_id: int):
    item = await db.get(Item, item_id)
    if not item:
        raise HTTPException(
            status_code=404,
            detail="Item not found"
        )
    return item
```

### Custom Exception Handlers

```python
class ItemNotFoundError(Exception):
    def __init__(self, item_id: int):
        self.item_id = item_id

@app.exception_handler(ItemNotFoundError)
async def item_not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"error": "Item not found", "item_id": exc.item_id}
    )
```

---

## Middleware

Code that runs for every request:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Common middleware:**
- CORS (Cross-Origin Resource Sharing)
- Authentication
- Logging
- Rate limiting

---

## Automatic Documentation

FastAPI generates docs automatically:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

Enhanced with Pydantic models:

```python
class HealthResponse(BaseModel):
    status: str
    timestamp: datetime

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"status": "healthy", "timestamp": "2024-01-15T10:30:00Z"}
            ]
        }
    }

@app.get("/health", response_model=HealthResponse)
async def health():
    """
    Check API health.

    Returns the current health status and timestamp.
    """
    return HealthResponse(status="healthy", timestamp=datetime.now())
```

The docstring becomes the endpoint description in the docs!

---

## Running the Application

### Development

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

| Flag | Purpose |
|------|---------|
| `app.main:app` | Python path to application |
| `--reload` | Auto-restart on code changes |
| `--host 0.0.0.0` | Accept connections from any IP |
| `--port 8000` | Listen on port 8000 |

### Production

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Or with Gunicorn (process manager):

```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

---

## Testing

```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
```

---

## Further Reading

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Starlette (underlying framework)](https://www.starlette.io/)
- [ASGI Specification](https://asgi.readthedocs.io/)
