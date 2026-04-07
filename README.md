# VisualVault

Smart Visual Asset Intelligence API - An ML-powered image analysis and search platform.

## Features

- **Image Upload & Storage**: Secure file uploads with validation
- **Visual Analysis**: Quality scoring, OCR, object detection
- **Similarity Search**: Find similar images using CLIP embeddings
- **Async Processing**: Background task processing with Celery
- **User Management**: API key authentication and rate limiting

## Quick Start

### With Docker (Recommended)

```bash
docker-compose up -d
```

### Local Development

```bash
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

```
visualvault/
├── app/
│   ├── api/v1/          # API endpoints
│   ├── models/          # SQLAlchemy models
│   ├── schemas/         # Pydantic schemas
│   ├── services/        # Business logic
│   ├── ml/              # ML models
│   └── workers/         # Celery tasks
├── tests/
├── storage/
└── docker-compose.yml
```

## License

MIT
