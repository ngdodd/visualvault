# VisualVault Makefile
# Common commands for development

.PHONY: help install dev test lint format run docker-up docker-down clean

# Default target
help:
	@echo "VisualVault - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install     Install production dependencies"
	@echo "  make dev         Install development dependencies"
	@echo ""
	@echo "Development:"
	@echo "  make run         Run development server"
	@echo "  make test        Run tests"
	@echo "  make lint        Run linter"
	@echo "  make format      Format code"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up   Start all services"
	@echo "  make docker-down Stop all services"
	@echo "  make docker-logs View logs"
	@echo ""
	@echo "Database:"
	@echo "  make db-migrate  Run database migrations"
	@echo "  make db-upgrade  Apply migrations"
	@echo "  make db-revision Create new migration"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean       Remove cache files"

# ===================
# Setup
# ===================
install:
	pip install -e .

dev:
	pip install -e ".[dev]"

# ===================
# Development
# ===================
run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=app --cov-report=html --cov-report=term

lint:
	ruff check app/ tests/
	mypy app/

format:
	ruff check --fix app/ tests/
	ruff format app/ tests/

# ===================
# Docker
# ===================
docker-up:
	docker-compose up -d

docker-up-build:
	docker-compose up -d --build

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-clean:
	docker-compose down -v --remove-orphans

# ===================
# Database
# ===================
db-migrate:
	alembic upgrade head

db-upgrade: db-migrate

db-revision:
	@read -p "Migration message: " msg; \
	alembic revision --autogenerate -m "$$msg"

db-downgrade:
	alembic downgrade -1

db-history:
	alembic history

# ===================
# Celery
# ===================
worker:
	celery -A app.workers.celery_app worker --loglevel=info -Q default,ml

flower:
	celery -A app.workers.celery_app flower --port=5555

# ===================
# Cleanup
# ===================
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf htmlcov/ .coverage 2>/dev/null || true
