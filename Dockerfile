# VisualVault Dockerfile
# Multi-stage build for optimized production images

# ===================
# Stage 1: Base image with Python and system deps
# ===================
FROM python:3.11-slim as base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    libjpeg-dev \
    libpng-dev \
    libgl1 \
    libglib2.0-0 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ===================
# Stage 2: Development image
# ===================
FROM base as development

# Copy project files
COPY pyproject.toml README.md ./
COPY app/ ./app/

# Install all dependencies including dev
RUN pip install --upgrade pip && \
    pip install -e ".[dev]"

# Copy remaining files (tests, etc.)
COPY . .

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ===================
# Stage 3: Production image
# ===================
FROM base as production

# Copy project files
COPY pyproject.toml README.md ./
COPY app/ ./app/

# Install production dependencies only
RUN pip install --upgrade pip && \
    pip install .

# Copy additional files
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser && \
    mkdir -p /app/storage/uploads /app/storage/embeddings /app/models && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
