# VisualVault - ML-Powered Visual Asset Intelligence API

A comprehensive teaching project demonstrating end-to-end API development with FastAPI, SQLAlchemy, Docker, Celery, and PyTorch/CLIP.

## Project Overview

VisualVault is a production-ready image analysis and search API that teaches students:

- **API Development**: REST API design, versioning, documentation
- **Database Management**: SQLAlchemy ORM, migrations, async queries
- **Authentication**: JWT tokens, API keys, password hashing
- **File Handling**: Secure uploads, validation, storage abstraction
- **Background Processing**: Celery task queues, retry logic
- **Machine Learning**: CLIP embeddings, similarity search, classification
- **Production Ops**: Rate limiting, caching, metrics, health checks

---

## Architecture

```
                                    VisualVault Architecture

    Client Request
          |
          v
    +------------------+      +------------------+      +------------------+
    |   Rate Limiter   |----->|  Request Logger  |----->|   Metrics        |
    |   (SlowAPI)      |      |  (Structlog)     |      |   (Prometheus)   |
    +------------------+      +------------------+      +------------------+
                                       |
                                       v
    +------------------+      +------------------+      +------------------+
    |   FastAPI        |----->|   SQLAlchemy     |----->|   PostgreSQL     |
    |   Endpoints      |      |   (Async)        |      |   Database       |
    +------------------+      +------------------+      +------------------+
          |
          |  Upload
          v
    +------------------+      +------------------+      +------------------+
    |   File Storage   |      |   Celery Task    |----->|   Redis          |
    |   (Local/S3)     |      |   Queue          |      |   Broker         |
    +------------------+      +------------------+      +------------------+
                                       |
                                       v
                              +------------------+
                              |   CLIP Model     |
                              |   (Embeddings)   |
                              +------------------+
```

---

## Project Structure

```
visualvault/
├── app/
│   ├── main.py                 # Application factory, lifespan
│   ├── config.py               # Pydantic settings
│   ├── database.py             # SQLAlchemy setup
│   ├── dependencies.py         # FastAPI dependencies
│   │
│   ├── api/v1/                 # API endpoints
│   │   ├── router.py           # Router aggregation
│   │   ├── auth.py             # Authentication endpoints
│   │   ├── assets.py           # Asset CRUD & upload
│   │   ├── search.py           # ML-powered search
│   │   └── health.py           # Health checks & metrics
│   │
│   ├── models/                 # SQLAlchemy models
│   │   ├── base.py             # Base model class
│   │   ├── user.py             # User model
│   │   └── asset.py            # Asset model
│   │
│   ├── schemas/                # Pydantic schemas
│   │   ├── common.py           # Shared schemas
│   │   ├── user.py             # User request/response
│   │   └── asset.py            # Asset request/response
│   │
│   ├── services/               # Business logic
│   │   ├── auth.py             # JWT, password hashing
│   │   ├── storage.py          # File storage abstraction
│   │   └── cache.py            # Redis caching
│   │
│   ├── middleware/             # Request middleware
│   │   ├── rate_limit.py       # SlowAPI rate limiting
│   │   ├── logging.py          # Request/response logging
│   │   └── metrics.py          # Prometheus metrics
│   │
│   ├── workers/                # Background tasks
│   │   ├── celery_app.py       # Celery configuration
│   │   └── tasks/
│   │       └── processing.py   # ML processing tasks
│   │
│   ├── ml/                     # Machine learning
│   │   └── clip_service.py     # CLIP embeddings & search
│   │
│   └── utils/                  # Utilities
│       └── image.py            # Image processing helpers
│
├── migrations/                 # Alembic migrations
│   ├── alembic.ini
│   ├── env.py
│   └── versions/
│
├── docs/                       # Module documentation
│   ├── module-01/              # Project Setup & FastAPI
│   ├── module-02/              # Database & Auth
│   ├── module-03/              # File Uploads
│   ├── module-04/              # Background Processing & ML
│   └── module-05/              # Production Readiness
│
├── tests/                      # Test suite
├── docker-compose.yml          # Local development stack
├── Dockerfile                  # Container image
└── requirements.txt            # Python dependencies
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Git

### 1. Clone and Setup

```bash
cd visualvault

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Start Infrastructure

```bash
# Start PostgreSQL, Redis
docker-compose up -d postgres redis
```

### 3. Configure Environment

```bash
# Copy example environment
cp .env.example .env

# Edit .env with your settings (or use defaults for local dev)
```

### 4. Run Database Migrations

```bash
# Create tables
alembic upgrade head
```

### 5. Start the API

```bash
# Development server with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 6. Start Celery Worker (separate terminal)

```bash
# Start background worker for ML processing
celery -A app.workers.celery_app worker --loglevel=info -Q ml
```

### 7. Access the API

- **API Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/api/v1/health

---

## Testing the API

### Create a User

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "SecurePass123"}'
```

### Login

```bash
curl -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test@example.com&password=SecurePass123"

# Save the access_token from response
export TOKEN="your-access-token-here"
```

### Upload an Image

```bash
curl -X POST http://localhost:8000/api/v1/assets/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/image.jpg"
```

### List Your Assets

```bash
curl http://localhost:8000/api/v1/assets \
  -H "Authorization: Bearer $TOKEN"
```

### Search by Text

```bash
curl -X POST http://localhost:8000/api/v1/search/text \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "a cat sitting on a couch", "limit": 5}'
```

### Check Health

```bash
# Simple health check
curl http://localhost:8000/api/v1/health

# Detailed health with all services
curl http://localhost:8000/api/v1/health/detailed

# Prometheus metrics
curl http://localhost:8000/api/v1/health/metrics
```

### Test Rate Limiting

```bash
# Send many requests quickly
for i in {1..100}; do
  curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/v1/health
done

# You should see 429 responses after hitting the limit
```

---

## Running with Docker

### Full Stack

```bash
# Build and start everything
docker-compose up --build

# This starts:
# - API server (port 8000)
# - PostgreSQL (port 5432)
# - Redis (port 6379)
# - Celery worker
```

### Individual Services

```bash
# Just database and cache
docker-compose up -d postgres redis

# Run API locally (for development)
uvicorn app.main:app --reload
```

---

## Module Breakdown

### Module 1: Project Setup & FastAPI Basics (2 hours)

**Topics:**
- Python project structure
- FastAPI fundamentals (routes, requests, responses)
- Pydantic for validation
- Docker basics
- API documentation (OpenAPI/Swagger)

**Key Files:** `app/main.py`, `app/config.py`, `docker-compose.yml`

**Documentation:** [docs/module-01/](docs/module-01/)

---

### Module 2: Database & Authentication (2.5 hours)

**Topics:**
- SQLAlchemy 2.0 async ORM
- Database migrations with Alembic
- JWT authentication
- API key authentication
- Password hashing with bcrypt

**Key Files:** `app/database.py`, `app/models/`, `app/services/auth.py`

**Documentation:** [docs/module-02/](docs/module-02/)

---

### Module 3: File Uploads & Storage (2 hours)

**Topics:**
- Multipart file uploads
- File validation (type, size)
- Storage abstraction (local/S3)
- Image processing with Pillow
- Secure file serving

**Key Files:** `app/services/storage.py`, `app/api/v1/assets.py`

**Documentation:** [docs/module-03/](docs/module-03/)

---

### Module 4: Background Processing & ML (2.5 hours)

**Topics:**
- Celery task queues
- Redis as message broker
- CLIP model for embeddings
- Similarity search
- Zero-shot classification

**Key Files:** `app/workers/`, `app/ml/clip_service.py`, `app/api/v1/search.py`

**Documentation:** [docs/module-04/](docs/module-04/)

---

### Module 5: Production Readiness (2 hours)

**Topics:**
- Rate limiting with SlowAPI
- Redis caching
- Structured logging
- Prometheus metrics
- Health checks
- Security hardening

**Key Files:** `app/middleware/`, `app/services/cache.py`, `app/api/v1/health.py`

**Documentation:** [docs/module-05/](docs/module-05/)

---

## Common Issues & Solutions

### "Database connection refused"
```bash
docker-compose up -d postgres
# Check DATABASE_URL in .env
```

### "Redis connection error"
```bash
docker-compose up -d redis
```

### "CLIP model download slow"
```bash
# Models download on first use (~400MB)
python -c "from transformers import CLIPModel; CLIPModel.from_pretrained('openai/clip-vit-base-patch32')"
```

### "Celery worker not processing"
```bash
celery -A app.workers.celery_app inspect active
```

---

## Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Web Framework | FastAPI | Async API with auto-docs |
| Database | PostgreSQL + SQLAlchemy 2.0 | Relational data storage |
| Migrations | Alembic | Schema versioning |
| Cache/Broker | Redis | Caching & task queue |
| Task Queue | Celery | Background processing |
| ML Model | CLIP (OpenAI) | Image embeddings |
| Auth | JWT + bcrypt | Token authentication |
| Rate Limiting | SlowAPI | Request throttling |
| Logging | Structlog | Structured JSON logs |
| Containers | Docker Compose | Local development |

---

## License

Educational use - AIM 230 Course
