# Understanding Project Structure

## Why Structure Matters

A well-organized project structure:
- Makes code **easy to find** - new team members can navigate quickly
- Enables **separation of concerns** - each directory has one job
- Supports **scalability** - easy to add new features without chaos
- Facilitates **testing** - clear boundaries make testing easier
- Follows **conventions** - familiar patterns for Python developers

Poor structure leads to:
- "Where does this code go?"
- Circular imports
- God files (one file doing everything)
- Difficult testing
- Onboarding nightmares

---

## The VisualVault Structure

```
visualvault/
├── app/                        # Main application package
│   ├── __init__.py
│   ├── main.py                 # Application entry point
│   ├── config.py               # Configuration management
│   ├── dependencies.py         # Shared FastAPI dependencies
│   │
│   ├── api/                    # API layer (HTTP interface)
│   │   ├── __init__.py
│   │   └── v1/                 # API version 1
│   │       ├── __init__.py
│   │       ├── router.py       # Aggregates all v1 routers
│   │       ├── health.py       # Health check endpoints
│   │       ├── auth.py         # Authentication endpoints
│   │       ├── assets.py       # Asset management endpoints
│   │       └── search.py       # Search endpoints
│   │
│   ├── models/                 # Database models (SQLAlchemy)
│   │   ├── __init__.py
│   │   ├── base.py             # Base model class
│   │   ├── user.py             # User model
│   │   └── asset.py            # Asset model
│   │
│   ├── schemas/                # Pydantic schemas (request/response)
│   │   ├── __init__.py
│   │   ├── common.py           # Shared schemas
│   │   ├── user.py             # User schemas
│   │   └── asset.py            # Asset schemas
│   │
│   ├── services/               # Business logic layer
│   │   ├── __init__.py
│   │   ├── auth.py             # Authentication logic
│   │   ├── asset.py            # Asset operations
│   │   └── storage.py          # File storage operations
│   │
│   ├── ml/                     # Machine Learning components
│   │   ├── __init__.py
│   │   ├── inference.py        # Model inference service
│   │   ├── preprocessing.py    # Input preprocessing
│   │   └── models/             # Model implementations
│   │       ├── __init__.py
│   │       ├── clip_encoder.py
│   │       └── quality_scorer.py
│   │
│   └── workers/                # Background task processing
│       ├── __init__.py
│       ├── celery_app.py       # Celery configuration
│       └── tasks/              # Task definitions
│           ├── __init__.py
│           ├── embedding.py
│           └── ocr.py
│
├── tests/                      # Test suite
│   ├── __init__.py
│   ├── conftest.py             # Pytest fixtures
│   ├── test_api/               # API endpoint tests
│   ├── test_ml/                # ML component tests
│   └── test_workers/           # Worker tests
│
├── alembic/                    # Database migrations
│   ├── versions/               # Migration files
│   └── env.py                  # Alembic configuration
│
├── storage/                    # File storage
│   ├── uploads/                # User uploaded files
│   └── embeddings/             # Generated embeddings
│
├── models/                     # ML model weights
│
├── scripts/                    # Utility scripts
│   ├── seed_db.py              # Database seeding
│   └── download_models.py      # Download ML models
│
├── docs/                       # Documentation
│   └── module-01/
│
├── pyproject.toml              # Project configuration
├── Dockerfile                  # Container build
├── docker-compose.yml          # Service orchestration
├── Makefile                    # Development commands
├── .env.example                # Environment template
├── .gitignore
└── README.md
```

---

## Directory Deep Dive

### The `app/` Package

This is your main application code. Everything here is Python that runs your API.

#### `app/main.py` - Entry Point

```python
# The application factory and startup
from app.api.v1.router import api_router

def create_app() -> FastAPI:
    app = FastAPI(...)
    app.include_router(api_router, prefix="/api/v1")
    return app

app = create_app()
```

**Responsibilities:**
- Create the FastAPI application
- Configure middleware
- Include routers
- Set up lifespan events

**Does NOT contain:**
- Endpoint implementations
- Business logic
- Database queries

#### `app/config.py` - Configuration

```python
# All configuration in one place
class Settings(BaseSettings):
    database: DatabaseSettings
    redis: RedisSettings
    # ...
```

**Why separate?**
- Single source of truth for configuration
- Easy to see all configurable options
- Testable (can create test configurations)

#### `app/dependencies.py` - Shared Dependencies

```python
# Reusable FastAPI dependencies
SettingsDep = Annotated[Settings, Depends(get_settings)]
DbSessionDep = Annotated[AsyncSession, Depends(get_db)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
```

**Why here?**
- Avoid circular imports
- Single place to find all dependencies
- Consistent naming conventions

---

### The `app/api/` Layer

Handles HTTP concerns: requests, responses, routing.

#### API Versioning: `app/api/v1/`

```
api/
└── v1/           # Version 1
    ├── router.py
    ├── health.py
    └── assets.py
```

**Why version?**
- Breaking changes go in `v2/`
- Existing clients keep working
- Gradual migration path

```python
# In main.py
app.include_router(v1_router, prefix="/api/v1")
app.include_router(v2_router, prefix="/api/v2")  # Future
```

#### `app/api/v1/router.py` - Route Aggregation

```python
from fastapi import APIRouter
from app.api.v1 import health, assets, auth

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(assets.router, prefix="/assets", tags=["Assets"])
```

**Why a separate router file?**
- See all routes in one place
- Control order and prefixes
- Easy to add/remove features

#### Endpoint Files: `health.py`, `assets.py`, etc.

```python
# app/api/v1/health.py
router = APIRouter()

@router.get("")
async def health_check():
    return {"status": "healthy"}
```

**Each file should:**
- Handle one resource or feature
- Define request/response validation
- Call services for business logic
- NOT contain database queries directly

---

### The `app/models/` Layer

SQLAlchemy database models - your data structure.

```python
# app/models/user.py
from sqlalchemy import Column, Integer, String
from app.models.base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True)
    hashed_password = Column(String)
```

**Models represent:**
- Database tables
- Relationships between tables
- Database-level constraints

**Models do NOT:**
- Contain business logic
- Handle HTTP requests
- Validate user input (that's schemas)

---

### The `app/schemas/` Layer

Pydantic models for request/response validation.

```python
# app/schemas/user.py
from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    """Schema for creating a user (request body)."""
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    """Schema for user in responses."""
    id: int
    email: str

    model_config = {"from_attributes": True}
```

**Why separate from models?**

| SQLAlchemy Model | Pydantic Schema |
|-----------------|-----------------|
| Database structure | API contract |
| Has `hashed_password` | Never exposes password |
| All fields | Only relevant fields |
| Database types | JSON-serializable types |

**Naming Convention:**
- `UserCreate` - For POST requests (creating)
- `UserUpdate` - For PUT/PATCH requests (updating)
- `UserResponse` - For responses
- `UserInDB` - Internal use, includes sensitive fields

---

### The `app/services/` Layer

Business logic - the "what" your application does.

```python
# app/services/auth.py
class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_user(self, data: UserCreate) -> User:
        # Business logic:
        # 1. Check if email exists
        # 2. Hash password
        # 3. Create user
        # 4. Send welcome email
        pass

    async def authenticate(self, email: str, password: str) -> User | None:
        # 1. Find user by email
        # 2. Verify password
        # 3. Return user or None
        pass
```

**Services should:**
- Contain business rules
- Orchestrate multiple operations
- Be testable without HTTP layer
- Handle transactions

**Services are used by endpoints:**

```python
# app/api/v1/auth.py
@router.post("/register")
async def register(data: UserCreate, db: DbSessionDep):
    service = AuthService(db)
    user = await service.create_user(data)
    return UserResponse.model_validate(user)
```

---

### The `app/ml/` Layer

Machine learning components, isolated from the API layer.

```
ml/
├── __init__.py
├── inference.py        # High-level inference API
├── preprocessing.py    # Input processing
└── models/            # Model implementations
    ├── clip_encoder.py
    └── quality_scorer.py
```

**Why separate?**
- ML code has different dependencies (PyTorch, etc.)
- Can be developed/tested independently
- May run on different hardware (GPU)
- Different expertise (ML engineers vs backend)

```python
# app/ml/models/clip_encoder.py
class CLIPEncoder:
    def __init__(self, model_path: str, device: str):
        self.model = load_model(model_path)
        self.device = device

    def encode(self, image: Image) -> np.ndarray:
        # Pure ML code, no FastAPI knowledge
        pass
```

```python
# app/ml/inference.py
class InferenceService:
    """High-level API for ML operations."""

    def __init__(self, settings: MLSettings):
        self.clip = CLIPEncoder(settings.clip_model_path, settings.device)

    async def get_embedding(self, image_path: Path) -> np.ndarray:
        image = load_image(image_path)
        return self.clip.encode(image)
```

---

### The `app/workers/` Layer

Background task processing with Celery.

```python
# app/workers/celery_app.py
from celery import Celery

celery_app = Celery("visualvault")
celery_app.config_from_object(settings)
```

```python
# app/workers/tasks/embedding.py
from app.workers.celery_app import celery_app

@celery_app.task
def generate_embedding(asset_id: int):
    # Long-running task
    # Runs in worker process, not API process
    pass
```

**Why workers?**
- Long operations (ML inference, video processing)
- Don't block API responses
- Can scale independently
- Retry failed tasks

---

### The `tests/` Directory

Mirrors the app structure:

```
tests/
├── conftest.py         # Shared fixtures
├── test_api/
│   ├── test_health.py  # Tests for app/api/v1/health.py
│   └── test_assets.py  # Tests for app/api/v1/assets.py
├── test_ml/
│   └── test_clip.py    # Tests for app/ml/models/clip_encoder.py
└── test_workers/
    └── test_embedding.py
```

**Naming Convention:** `test_<module>.py` tests `<module>.py`

---

### Supporting Directories

#### `alembic/` - Database Migrations

```
alembic/
├── versions/           # Migration files
│   ├── 001_create_users.py
│   └── 002_add_assets.py
└── env.py             # Migration configuration
```

Track database schema changes over time.

#### `storage/` - File Storage

```
storage/
├── uploads/           # User-uploaded files
└── embeddings/        # Generated vector embeddings
```

Separate from code, can be mounted as a volume.

#### `scripts/` - Utility Scripts

```
scripts/
├── seed_db.py         # Populate database with test data
└── download_models.py  # Download ML model weights
```

One-off operations, not part of the main app.

---

## Layered Architecture

```
┌─────────────────────────────────────────────┐
│                API Layer                     │
│         (app/api/v1/*.py)                   │
│    HTTP handling, validation, routing        │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│              Service Layer                   │
│          (app/services/*.py)                │
│     Business logic, orchestration           │
└──────────────────┬──────────────────────────┘
                   │
         ┌─────────┴─────────┐
         ▼                   ▼
┌─────────────────┐   ┌─────────────────┐
│   Data Layer    │   │    ML Layer     │
│ (app/models/)   │   │   (app/ml/)     │
│   Database      │   │   Inference     │
└─────────────────┘   └─────────────────┘
```

**Rules:**
- Upper layers can call lower layers
- Lower layers never call upper layers
- Same-level calls are OK within a layer

---

## Import Guidelines

### Good Imports

```python
# api/ imports from services/
from app.services.auth import AuthService

# services/ imports from models/
from app.models.user import User

# api/ imports from schemas/
from app.schemas.user import UserCreate, UserResponse
```

### Avoid Circular Imports

```python
# BAD: services/ importing from api/
# app/services/auth.py
from app.api.v1.auth import router  # NEVER DO THIS
```

**If you have circular imports:** Your structure is wrong. Refactor.

---

## Adding a New Feature

Let's say we're adding "Collections" (groups of assets):

1. **Model:** `app/models/collection.py`
2. **Schemas:** `app/schemas/collection.py`
3. **Service:** `app/services/collection.py`
4. **Endpoints:** `app/api/v1/collections.py`
5. **Tests:** `tests/test_api/test_collections.py`
6. **Router:** Add to `app/api/v1/router.py`

Each layer handles its responsibility. The structure guides you.

---

## Common Patterns

### Repository Pattern (Optional)

Add a layer between services and models:

```
services/ → repositories/ → models/
```

```python
# app/repositories/user.py
class UserRepository:
    async def get_by_email(self, email: str) -> User | None:
        return await self.db.query(User).filter(User.email == email).first()

    async def create(self, user: User) -> User:
        self.db.add(user)
        await self.db.commit()
        return user
```

**Benefits:**
- Services don't know about SQLAlchemy
- Easy to mock for testing
- Could swap databases (SQL → NoSQL)

### Feature-Based Structure (Alternative)

Group by feature instead of layer:

```
app/
├── users/
│   ├── models.py
│   ├── schemas.py
│   ├── services.py
│   ├── routes.py
│   └── tests.py
├── assets/
│   ├── models.py
│   └── ...
```

**Trade-offs:**
- Easier to see all code for one feature
- Harder to see all models or all routes
- Good for large teams (team per feature)

---

## Summary

| Directory | Purpose | Contains |
|-----------|---------|----------|
| `app/api/` | HTTP layer | Routes, validation |
| `app/models/` | Data layer | Database tables |
| `app/schemas/` | Contracts | Request/response shapes |
| `app/services/` | Business | Logic, orchestration |
| `app/ml/` | Intelligence | ML models, inference |
| `app/workers/` | Background | Async tasks |
| `tests/` | Quality | All tests |

**The golden rule:** If you're unsure where code goes, ask "What is this code's responsibility?" and put it in the matching layer.
