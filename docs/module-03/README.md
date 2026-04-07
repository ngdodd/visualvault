# Module 3: File Uploads & Storage

## Overview

This module adds file upload capabilities to VisualVault. You'll learn how to handle file uploads securely, store files efficiently, and track uploaded assets in the database.

## Learning Objectives

By completing this module, you will be able to:

1. **Handle file uploads** - Process multipart form data with FastAPI
2. **Validate uploads** - Check file types, sizes, and image integrity
3. **Design a storage abstraction** - Create a backend-agnostic storage service
4. **Track assets** - Store metadata and processing status in the database
5. **Serve files securely** - Download files with proper authentication
6. **Process images** - Extract dimensions and validate image data

---

## Prerequisites

- Completed Module 2 (Database & Authentication)
- Docker containers running (`docker-compose up -d`)
- Migrations applied (`alembic upgrade head`)

---

## Lesson Plan

### Part 1: Understanding File Uploads (15 min)

**Concepts:**
- Multipart form data encoding
- Streaming vs buffered uploads
- Memory considerations for large files

**Key Code:** Upload endpoint with FastAPI

```python
from fastapi import File, UploadFile

@router.post("/upload")
async def upload_image(
    file: UploadFile = File(...),
):
    content = await file.read()  # Read file content
    # Process the file...
```

**Key Takeaway:** FastAPI's `UploadFile` provides a file-like interface with automatic cleanup. For large files, read in chunks to avoid memory issues.

**Read More:** [01-file-uploads.md](./01-file-uploads.md)

---

### Part 2: File Validation (20 min)

**Concepts:**
- MIME type validation
- File size limits
- Image integrity checking
- Security considerations

**Key Code:** `app/services/storage.py`

```python
ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}

def validate_image(content_type: str, file_size: int) -> tuple[bool, str]:
    if content_type not in ALLOWED_IMAGE_TYPES:
        return False, f"File type '{content_type}' not allowed"

    if file_size > MAX_FILE_SIZE:
        return False, f"File too large"

    return True, ""
```

**Key Takeaway:** Never trust client-provided MIME types. Use libraries like Pillow to verify the actual file format.

**Read More:** [02-file-validation.md](./02-file-validation.md)

---

### Part 3: Storage Service Abstraction (25 min)

**Concepts:**
- Storage backend interface
- Local filesystem storage
- Preparing for cloud storage (S3)
- File organization strategies

**Key Code:** `app/services/storage.py`

```python
class StorageBackend(ABC):
    @abstractmethod
    async def save(self, file, filename, user_id) -> str:
        """Save file, return storage path."""
        pass

    @abstractmethod
    async def get(self, path) -> Path | None:
        """Get local path for serving."""
        pass

    @abstractmethod
    async def delete(self, path) -> bool:
        """Delete a file."""
        pass


class LocalStorageBackend(StorageBackend):
    def __init__(self, base_path: Path):
        self.base_path = base_path

    async def save(self, file, filename, user_id) -> str:
        # Organize by user_id and date
        user_path = self.base_path / str(user_id) / "2024/01"
        user_path.mkdir(parents=True, exist_ok=True)
        # Generate unique filename, save file...
```

**Key Takeaway:** Abstract storage operations behind an interface. This allows switching from local storage to S3 without changing application code.

**Read More:** [03-storage-service.md](./03-storage-service.md)

---

### Part 4: Asset Model & Tracking (20 min)

**Concepts:**
- Asset lifecycle (pending → processing → completed)
- Storing file metadata
- Relationships to users
- Indexing for efficient queries

**Key Code:** `app/models/asset.py`

```python
class AssetStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Asset(Base, TimestampMixin):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    # File info
    filename: Mapped[str] = mapped_column(String(255))
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    file_size: Mapped[int]
    storage_path: Mapped[str] = mapped_column(String(500))

    # Dimensions
    width: Mapped[int | None]
    height: Mapped[int | None]

    # Status
    status: Mapped[str] = mapped_column(default=AssetStatus.PENDING.value)
```

**Key Takeaway:** Track both the physical file (storage_path) and logical metadata (filename, dimensions) in the database. The status field enables async processing workflows.

**Read More:** [04-asset-model.md](./04-asset-model.md)

---

### Part 5: Image Utilities (15 min)

**Concepts:**
- Extracting image dimensions
- Creating thumbnails
- Validating image integrity
- Color extraction

**Key Code:** `app/utils/image.py`

```python
from PIL import Image

def get_image_dimensions(file: BinaryIO) -> tuple[int, int] | None:
    try:
        img = Image.open(file)
        dimensions = img.size  # (width, height)
        file.seek(0)  # Reset for later use
        return dimensions
    except Exception:
        file.seek(0)
        return None


def validate_image_integrity(file: BinaryIO) -> tuple[bool, str]:
    try:
        img = Image.open(file)
        img.verify()  # Check for corruption
        file.seek(0)
        return True, ""
    except Exception as e:
        file.seek(0)
        return False, f"Invalid image: {e}"
```

**Key Takeaway:** Always reset file position after reading. The `verify()` method checks image integrity without fully loading it into memory.

**Read More:** [05-image-processing.md](./05-image-processing.md)

---

## Hands-On Exercises

### Exercise 1: Upload an Image

```bash
# Get an auth token first
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"YourPass123"}' | jq -r '.access_token')

# Upload an image
curl -X POST http://localhost:8000/api/v1/assets/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/image.jpg"
```

### Exercise 2: List Assets

```bash
curl http://localhost:8000/api/v1/assets \
  -H "Authorization: Bearer $TOKEN"
```

### Exercise 3: Download Asset

```bash
# Get asset ID from list response
curl http://localhost:8000/api/v1/assets/1/file \
  -H "Authorization: Bearer $TOKEN" \
  --output downloaded.jpg
```

### Exercise 4: Test Validation

```bash
# Try uploading a non-image file
curl -X POST http://localhost:8000/api/v1/assets/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/document.pdf"
# Should return 400 Bad Request
```

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `app/models/asset.py` | Asset model with status tracking |
| `app/schemas/asset.py` | Pydantic schemas for requests/responses |
| `app/services/storage.py` | Storage abstraction layer |
| `app/utils/image.py` | Image processing utilities |
| `app/api/v1/assets.py` | Upload and management endpoints |
| `alembic/versions/002_*.py` | Assets table migration |

---

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/v1/assets/upload` | Yes | Upload single image |
| POST | `/api/v1/assets/upload/batch` | Yes | Upload multiple images |
| GET | `/api/v1/assets` | Yes | List user's assets |
| GET | `/api/v1/assets/{id}` | Yes | Get asset details |
| GET | `/api/v1/assets/{id}/file` | Yes | Download original file |
| DELETE | `/api/v1/assets/{id}` | Yes | Delete asset |

---

## Common Issues & Solutions

### "File type not allowed"
**Cause:** Uploading a non-image file or incorrect MIME type.
**Solution:** Ensure the file is a supported image format (JPEG, PNG, GIF, WebP).

### "File too large"
**Cause:** File exceeds the configured maximum size.
**Solution:** Increase `STORAGE_MAX_FILE_SIZE_MB` or resize the image before uploading.

### "Invalid or corrupted image"
**Cause:** The file is not a valid image or is corrupted.
**Solution:** Verify the file opens correctly in an image viewer.

### "Storage service not initialized"
**Cause:** `init_storage()` not called at startup.
**Solution:** Ensure it's in the lifespan context manager in `main.py`.

---

## Security Checklist

- [ ] Validate file types server-side (don't trust Content-Type)
- [ ] Enforce file size limits
- [ ] Store files outside the web root
- [ ] Generate unique filenames (prevent overwrites)
- [ ] Authenticate file downloads
- [ ] Scan uploads for malware (production consideration)

---

## What's Next: Module 4

In Module 4, we'll add:
- **Celery task queue** for background processing
- **ML model integration** for image analysis
- **Feature extraction** (labels, colors, text)
- **Embedding generation** for similarity search

---

## Additional Resources

- [FastAPI File Uploads](https://fastapi.tiangolo.com/tutorial/request-files/)
- [Pillow Documentation](https://pillow.readthedocs.io/)
- [Python Pathlib Guide](https://docs.python.org/3/library/pathlib.html)
- [OWASP File Upload Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html)
