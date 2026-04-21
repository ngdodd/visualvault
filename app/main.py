"""
VisualVault - Main Application Entry Point

This module demonstrates:
- FastAPI application factory pattern
- Lifespan context manager for startup/shutdown events
- CORS middleware configuration
- Router inclusion with API versioning
- Health check endpoints
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.config import Settings, get_settings
from app.database import close_db, init_db
from app.services.storage import init_storage
from app.services.cache import init_cache, close_cache
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.metrics import MetricsMiddleware
from app.middleware.rate_limit import limiter, rate_limit_exceeded_handler
from app.ml.clip_service import init_clip_service
from app.ml.yolo_service import init_yolo_service
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer() if not get_settings().debug else structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Lifespan context manager for FastAPI application.

    This replaces the deprecated @app.on_event("startup") and
    @app.on_event("shutdown") decorators.

    Use this for:
    - Database connection pool initialization
    - ML model loading
    - Cache warming
    - Cleanup on shutdown
    """
    settings = get_settings()

    # === STARTUP ===
    logger.info(
        "Starting VisualVault API",
        environment=settings.environment,
        debug=settings.debug,
    )

    # Ensure storage directories exist
    settings.storage.uploads_path.mkdir(parents=True, exist_ok=True)
    settings.storage.embeddings_path.mkdir(parents=True, exist_ok=True)
    logger.info("Storage directories initialized", path=str(settings.storage.base_path))

    # Initialize storage service
    init_storage(settings)
    logger.info("Storage service initialized")

    # Initialize database connection pool
    init_db(settings)
    logger.info("Database connection pool initialized")

    # Initialize cache service
    await init_cache(settings)
    logger.info("Cache service initialized")

    # Pre-load CLIP model for search (avoids slow first request)
    logger.info("Loading CLIP model (this may take a minute on first run)...")
    init_clip_service(settings)
    logger.info("CLIP model loaded")

    # Pre-load YOLO model for object detection
    logger.info("Loading YOLO model (default: yolov8n)...")
    init_yolo_service()
    logger.info("YOLO model loaded")

    yield  # Application runs here

    # === SHUTDOWN ===
    logger.info("Shutting down VisualVault API")

    # Close cache connections
    await close_cache()
    logger.info("Cache connections closed")

    # Close database connections
    await close_db()
    logger.info("Database connections closed")


def create_app(settings: Settings | None = None) -> FastAPI:
    """
    Application factory function.

    This pattern allows:
    - Easy testing with different configurations
    - Multiple app instances if needed
    - Clear separation of configuration and initialization

    Args:
        settings: Optional settings override (useful for testing)

    Returns:
        FastAPI: Configured application instance
    """
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="""
## VisualVault - Smart Visual Asset Intelligence API

An ML-powered platform for image analysis, search, and management.

### Features
- **Image Upload & Storage**: Secure file uploads with validation
- **Visual Analysis**: Quality scoring, OCR, object detection
- **Similarity Search**: Find similar images using embeddings
- **Async Processing**: Background task processing with Celery
- **User Management**: API key authentication and rate limiting
        """,
        docs_url="/docs" if settings.debug else None,  # Disable docs in production
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add custom middleware (order matters - first added = outermost)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

    # Configure rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    # Include API routers
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    return app


# Create the application instance
app = create_app()
