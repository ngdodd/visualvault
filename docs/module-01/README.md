# Module 1: FastAPI Foundations & Project Setup

## Overview

This module establishes the foundation for building a production-ready ML API. By the end, you'll have a fully containerized FastAPI application with proper configuration management, health checks, and a scalable project structure.

## Learning Objectives

By completing this module, you will be able to:

1. **Understand FastAPI fundamentals** - Create async endpoints, use dependency injection, and define response models
2. **Configure applications with Pydantic Settings** - Type-safe configuration from environment variables
3. **Structure a production ML project** - Organize code for maintainability and scalability
4. **Containerize with Docker** - Write multi-stage Dockerfiles and understand image optimization
5. **Orchestrate services with Docker Compose** - Run multi-container applications locally
6. **Implement health check patterns** - Liveness and readiness probes for container orchestration

---

## Prerequisites

- Python 3.10+
- Docker Desktop installed and running
- Basic understanding of Python, REST APIs, and command line

---

## Project: VisualVault

We're building **VisualVault** - a smart visual asset intelligence API that will eventually support:
- Image upload and storage
- ML-powered analysis (quality scoring, OCR, object detection)
- Similarity search using embeddings
- User authentication and rate limiting

In Module 1, we focus on the **foundation** - getting the project structure, configuration, and containerization right.

---

## Lesson Plan

### Part 1: Project Structure (15 min)

**Concepts:**
- Why project structure matters for ML applications
- Separation of concerns (API, models, services, ML, workers)
- The `app/` package pattern

**Files Created:**
```
visualvault/
├── app/
│   ├── __init__.py
│   ├── main.py           # Application entry point
│   ├── config.py         # Configuration management
│   ├── dependencies.py   # Dependency injection
│   ├── api/v1/           # API endpoints (versioned)
│   ├── models/           # Database models (Module 2)
│   ├── schemas/          # Pydantic schemas
│   ├── services/         # Business logic
│   ├── ml/               # ML components
│   └── workers/          # Background tasks
├── tests/
├── storage/
└── pyproject.toml
```

**Key Takeaway:** A well-organized structure makes it easier to navigate, test, and scale your application.

**Read More:** [05-project-structure.md](./05-project-structure.md)

---

### Part 2: Pydantic Settings & Configuration (20 min)

**Concepts:**
- Environment-based configuration
- Type validation for config values
- Nested configuration models
- The `@lru_cache` pattern for settings

**Key Code:** `app/config.py`

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "VisualVault"
    debug: bool = False
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)

    model_config = SettingsConfigDict(env_file=".env")

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

**Key Takeaway:** Pydantic Settings provides type-safe configuration with automatic environment variable loading and validation.

**Read More:** [04-pydantic-settings.md](./04-pydantic-settings.md)

---

### Part 3: FastAPI Application Factory (25 min)

**Concepts:**
- The application factory pattern (`create_app()`)
- Lifespan context managers for startup/shutdown
- CORS middleware configuration
- Router organization and API versioning

**Key Code:** `app/main.py`

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting application")
    yield
    # Shutdown
    logger.info("Shutting down")

def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.include_router(api_router, prefix="/api/v1")
    return app
```

**Key Takeaway:** The factory pattern enables testing with different configurations and clean separation of initialization logic.

**Read More:** [03-fastapi-basics.md](./03-fastapi-basics.md)

---

### Part 4: Health Check Endpoints (20 min)

**Concepts:**
- Liveness vs Readiness probes
- Component health checking
- Pydantic response models with examples
- Dependency injection in endpoints

**Key Code:** `app/api/v1/health.py`

```python
@router.get("/ready", response_model=DetailedHealthResponse)
async def readiness_check(
    settings: Annotated[Settings, Depends(get_settings)],
) -> DetailedHealthResponse:
    components = {}
    components["storage"] = await check_storage_health(settings)
    # Check other components...
    return DetailedHealthResponse(status=overall_status, components=components)
```

**Key Takeaway:** Health endpoints are critical for container orchestration (Kubernetes) and monitoring systems.

---

### Part 5: Dockerfile Deep Dive (25 min)

**Concepts:**
- Multi-stage builds
- Layer caching optimization
- Development vs Production targets
- Security best practices (non-root user)

**Key Code:** `Dockerfile`

```dockerfile
FROM python:3.11-slim as base
# Install system dependencies...

FROM base as development
COPY pyproject.toml README.md ./
COPY app/ ./app/
RUN pip install -e ".[dev]"
CMD ["uvicorn", "app.main:app", "--reload"]

FROM base as production
RUN pip install .
CMD ["uvicorn", "app.main:app", "--workers", "4"]
```

**Key Takeaway:** Multi-stage builds create smaller, more secure production images while maintaining developer convenience.

**Read More:** [01-dockerfile.md](./01-dockerfile.md)

---

### Part 6: Docker Compose Orchestration (20 min)

**Concepts:**
- Service definitions and dependencies
- Health checks and startup order
- Volume mounts for development
- Environment variable injection

**Key Code:** `docker-compose.yml`

```yaml
services:
  api:
    build:
      context: .
      target: development
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - ./app:/app/app:ro
```

**Key Takeaway:** Docker Compose simplifies running multi-container applications by defining the entire stack in one file.

**Read More:** [02-docker-compose.md](./02-docker-compose.md)

---

### Part 7: Testing Setup (15 min)

**Concepts:**
- Pytest fixtures and configuration
- FastAPI TestClient
- Test organization

**Key Code:** `tests/conftest.py`

```python
@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client
```

---

## Hands-On Exercises

### Exercise 1: Explore the API
```bash
# Start the services
docker-compose up -d

# Test health endpoints
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/health/ready

# View API documentation
open http://localhost:8000/docs
```

### Exercise 2: Modify Configuration
1. Edit `.env` to change `DEBUG=false`
2. Restart the API: `docker-compose restart api`
3. Try to access `/docs` - it should be disabled

### Exercise 3: Add a New Endpoint
1. Create `app/api/v1/info.py` with a `/info` endpoint
2. Return application metadata (name, version, environment)
3. Include it in the router
4. Test it works

### Exercise 4: Run Tests
```bash
# Install dev dependencies locally
pip install -e ".[dev]"

# Run tests
pytest tests/ -v
```

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `app/main.py` | Application factory and lifespan |
| `app/config.py` | Pydantic Settings configuration |
| `app/dependencies.py` | Reusable FastAPI dependencies |
| `app/api/v1/router.py` | API router aggregation |
| `app/api/v1/health.py` | Health check endpoints |
| `app/schemas/common.py` | Shared Pydantic schemas |
| `Dockerfile` | Container build instructions |
| `docker-compose.yml` | Service orchestration |
| `pyproject.toml` | Python project configuration |

---

## Common Issues & Solutions

### Docker Desktop not running
```
Error: open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file
```
**Solution:** Start Docker Desktop and wait for it to fully initialize.

### Port already in use
```
Error: bind: address already in use
```
**Solution:** Stop the conflicting service or change the port in docker-compose.yml.

### Module not found errors
```
ModuleNotFoundError: No module named 'app'
```
**Solution:** Ensure you're running from the project root and the package is installed.

---

## What's Next: Module 2

In Module 2, we'll add:
- **SQLAlchemy async models** for User and APIKey
- **Alembic migrations** for database schema management
- **Database session dependency** injection
- **User registration endpoint** with password hashing

---

## Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [Docker Documentation](https://docs.docker.com/)
- [Twelve-Factor App Methodology](https://12factor.net/)
