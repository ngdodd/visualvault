# Assignment: Building an ML API Service

## Overview

In this assignment, you will create a REST API that exposes your machine learning model as a web service. You'll use FastAPI for the API framework and Docker for containerization, making your model accessible to any application that can make HTTP requests.

**No databases or authentication required** - focus on getting your model working as an API.

---

## Learning Objectives

By completing this assignment, you will be able to:

1. Structure a FastAPI application for ML inference
2. Create endpoints that accept various input types (JSON, files, images)
3. Load and use ML models within an API context
4. Containerize your application with Docker
5. Use Docker Compose for local deployment
6. Document your API with OpenAPI/Swagger

---

## Reference Implementation

Use the VisualVault project as your reference:

| What You Need | Reference File |
|---------------|----------------|
| FastAPI app structure | `visualvault/app/main.py` |
| Pydantic schemas | `visualvault/app/schemas/` |
| ML model service | `visualvault/app/ml/clip_service.py` |
| Dockerfile | `visualvault/Dockerfile` |
| Docker Compose | `visualvault/docker-compose.yml` |

---

## Requirements

### 1. Project Structure

Create a clean project structure:

```
your-project/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration/settings
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── inference.py     # Request/response schemas
│   ├── services/
│   │   ├── __init__.py
│   │   └── model.py         # Your ML model service
│   └── api/
│       ├── __init__.py
│       └── endpoints.py     # API endpoints
├── models/                   # Store model weights here
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

### 2. ML Model Service

Create a service class that wraps your ML model:

```python
# app/services/model.py

class YourModelService:
    def __init__(self):
        self.model = None
        self._initialized = False

    def initialize(self):
        """Load your model here."""
        if self._initialized:
            return

        # Example: Load a sklearn model
        # self.model = joblib.load("models/your_model.pkl")

        # Example: Load a PyTorch model
        # self.model = torch.load("models/your_model.pt")
        # self.model.eval()

        # Example: Load a HuggingFace model
        # self.model = pipeline("sentiment-analysis")

        self._initialized = True

    def predict(self, input_data):
        """Run inference on input data."""
        self.initialize()  # Lazy loading

        # Your inference logic here
        result = self.model.predict(input_data)

        return result

# Global instance
_model_service = None

def get_model_service():
    global _model_service
    if _model_service is None:
        _model_service = YourModelService()
    return _model_service
```

**Reference:** See `visualvault/app/ml/clip_service.py` for a complete example with CLIP.

### 3. API Endpoints

Create at least **two endpoints**:

1. **Health Check** - Verify the API is running
2. **Prediction Endpoint** - Run inference with your model

```python
# app/api/endpoints.py

from fastapi import APIRouter, HTTPException
from app.schemas.inference import PredictionRequest, PredictionResponse
from app.services.model import get_model_service

router = APIRouter()

@router.get("/health")
async def health_check():
    """Check if the API is running."""
    return {"status": "healthy", "model": "your-model-name"}

@router.post("/predict", response_model=PredictionResponse)
async def predict(request: PredictionRequest):
    """
    Run inference with your ML model.

    Describe what your model does and what inputs it expects.
    """
    try:
        model_service = get_model_service()
        result = model_service.predict(request.data)
        return PredictionResponse(prediction=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### 4. Request/Response Schemas

Use Pydantic for input validation:

```python
# app/schemas/inference.py

from pydantic import BaseModel, Field
from typing import List, Optional

class PredictionRequest(BaseModel):
    """Define your input schema based on what your model needs."""

    # Example for text input:
    text: str = Field(..., description="Text to analyze")

    # Example for numeric features:
    # features: List[float] = Field(..., description="Input features")

    # Example for image URL:
    # image_url: str = Field(..., description="URL of image to process")

    class Config:
        json_schema_extra = {
            "example": {
                "text": "This is a sample input"
            }
        }

class PredictionResponse(BaseModel):
    """Define your output schema."""
    prediction: str  # or List[float], dict, etc.
    confidence: Optional[float] = None

    # Add any other fields your model returns
```

**Reference:** See `visualvault/app/schemas/asset.py` for more complex examples.

### 5. Main Application

```python
# app/main.py

from fastapi import FastAPI
from app.api.endpoints import router
from app.services.model import get_model_service

app = FastAPI(
    title="Your ML API",
    description="Describe what your ML model does",
    version="1.0.0",
)

@app.on_event("startup")
async def startup():
    """Pre-load the model on startup (optional but recommended)."""
    print("Loading ML model...")
    service = get_model_service()
    service.initialize()
    print("Model loaded!")

# Include your router
app.include_router(router, prefix="/api/v1", tags=["inference"])
```

**Reference:** See `visualvault/app/main.py` for the lifespan pattern (newer approach).

### 6. Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (if needed)
# RUN apt-get update && apt-get install -y libgl1 && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ app/
COPY models/ models/

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Reference:** See `visualvault/Dockerfile` for a multi-stage build example.

### 7. Docker Compose

```yaml
# docker-compose.yml

services:
  api:
    build: .
    ports:
      - "8000:8000"
    volumes:
      # Mount models directory (so you don't rebuild for model updates)
      - ./models:/app/models
    environment:
      - MODEL_PATH=/app/models/your_model.pkl
```

**Reference:** See `visualvault/docker-compose.yml` for a more complete setup.

---

## Handling Different Input Types

### JSON Input (structured data)

```python
class TabularRequest(BaseModel):
    features: List[float]

@router.post("/predict")
async def predict(request: TabularRequest):
    result = model.predict([request.features])
    return {"prediction": result[0]}
```

### File Upload (images, documents)

```python
from fastapi import File, UploadFile

@router.post("/predict/image")
async def predict_image(file: UploadFile = File(...)):
    # Read file content
    content = await file.read()

    # Process with PIL for images
    from PIL import Image
    import io
    image = Image.open(io.BytesIO(content))

    # Run inference
    result = model.predict(image)
    return {"prediction": result}
```

**Reference:** See `visualvault/app/api/v1/assets.py` for file upload handling.

### Text Input

```python
class TextRequest(BaseModel):
    text: str

@router.post("/predict/text")
async def predict_text(request: TextRequest):
    result = model.predict(request.text)
    return {"prediction": result}
```

---

## Example Use Cases

Adapt based on your ML project:

| Use Case | Input Type | Output Type |
|----------|------------|-------------|
| Sentiment Analysis | Text (JSON) | Label + Confidence |
| Image Classification | Image (File Upload) | Labels + Probabilities |
| Object Detection | Image (File Upload) | Bounding Boxes + Labels |
| Recommendation | User/Item IDs (JSON) | Ranked List |
| Regression | Feature Vector (JSON) | Numeric Value |
| Text Generation | Prompt (JSON) | Generated Text |
| Similarity Search | Text or Image | Ranked Results |

---

## Deliverables

### Required Files

1. **Source Code**
   - `app/` directory with all Python files
   - `Dockerfile`
   - `docker-compose.yml`
   - `requirements.txt`

2. **Documentation**
   - `README.md` with:
     - Project description
     - How to run locally
     - How to run with Docker
     - API endpoint documentation
     - Example requests/responses

3. **Model Files**
   - Include your trained model in `models/` directory
   - Or document how to download it (for large models)

### Submission

- GitHub repository link
- Screenshot of Swagger docs (`/docs` endpoint)
- Screenshot of successful API call

---

## Grading Rubric

| Criteria | Points |
|----------|--------|
| **Project Structure** - Clean, organized code following the template | 15 |
| **ML Model Service** - Proper model loading and inference | 20 |
| **API Endpoints** - Working health and prediction endpoints | 20 |
| **Input Validation** - Pydantic schemas with proper types | 10 |
| **Docker** - Working Dockerfile and docker-compose.yml | 20 |
| **Documentation** - Clear README with usage instructions | 10 |
| **Code Quality** - Readable, commented where necessary | 5 |
| **Total** | **100** |

### Bonus Points (+10 max)

- Multiple prediction endpoints for different use cases
- Batch prediction endpoint
- Response caching
- Error handling with informative messages
- Unit tests

---

## Getting Started Checklist

- [ ] Create project directory structure
- [ ] Set up virtual environment: `python -m venv venv`
- [ ] Install FastAPI: `pip install fastapi uvicorn pydantic`
- [ ] Install your ML framework (torch, sklearn, transformers, etc.)
- [ ] Create basic `main.py` with health endpoint
- [ ] Test locally: `uvicorn app.main:app --reload`
- [ ] Visit http://localhost:8000/docs to see Swagger UI
- [ ] Add your model service
- [ ] Add prediction endpoint
- [ ] Create Dockerfile
- [ ] Create docker-compose.yml
- [ ] Test with Docker: `docker-compose up --build`
- [ ] Write README
- [ ] Submit!

---

## Common Issues & Solutions

### "Model file not found"
- Check your model path in the Dockerfile COPY command
- Verify the path in your model service matches

### "Module not found" in Docker
- Make sure all dependencies are in `requirements.txt`
- Rebuild with `docker-compose up --build`

### Slow first request
- Pre-load model in startup event (see Section 5)
- Consider model quantization for large models

### Out of memory
- Use smaller batch sizes
- Consider CPU-only inference: `torch.device("cpu")`
- Use model quantization

### File upload not working
- Install `python-multipart`: `pip install python-multipart`
- Check file size limits in uvicorn/nginx

---

## Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Docker Documentation](https://docs.docker.com/)
- [VisualVault Reference Code](../../../app/)

---

## Questions?

If you get stuck:
1. Check the VisualVault reference implementation
2. Review FastAPI documentation
3. Ask away!
