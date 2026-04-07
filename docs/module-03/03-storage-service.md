# Storage Service: Abstraction for File Management

## Why Abstract Storage?

Your application shouldn't care *where* files are stored:

```
Development    →  Local filesystem  → /storage/uploads/
Staging        →  MinIO (S3-compatible) → bucket/uploads/
Production     →  AWS S3            → s3://my-bucket/uploads/
```

With a storage abstraction, switching backends is a configuration change.

---

## The Storage Backend Interface

```python
# app/services/storage.py

from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO

class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    async def save(
        self,
        file: BinaryIO,
        filename: str,
        content_type: str,
        user_id: int,
    ) -> str:
        """
        Save a file to storage.

        Args:
            file: File-like object with the content
            filename: Original filename
            content_type: MIME type
            user_id: Owner's user ID

        Returns:
            Storage path/key for retrieval
        """
        pass

    @abstractmethod
    async def get(self, path: str) -> Path | None:
        """
        Get local path to serve a file.

        For remote storage, this might download to a temp file.

        Returns:
            Local filesystem path, or None if not found
        """
        pass

    @abstractmethod
    async def delete(self, path: str) -> bool:
        """
        Delete a file from storage.

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """Check if a file exists."""
        pass
```

---

## Local Storage Implementation

```python
import shutil
import uuid
from datetime import datetime
from pathlib import Path

class LocalStorageBackend(StorageBackend):
    """
    Local filesystem storage.

    Files are organized by user and date:
    uploads/
      └── {user_id}/
          └── {year}/{month}/
              └── {unique_filename}
    """

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _generate_unique_filename(self, original: str) -> str:
        """Generate a unique, safe filename."""
        ext = Path(original).suffix.lower()
        unique_id = uuid.uuid4().hex[:16]
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        return f"{timestamp}_{unique_id}{ext}"

    def _get_user_path(self, user_id: int) -> Path:
        """Get organized path for user's files."""
        now = datetime.utcnow()
        return self.base_path / str(user_id) / str(now.year) / f"{now.month:02d}"

    async def save(
        self,
        file: BinaryIO,
        filename: str,
        content_type: str,
        user_id: int,
    ) -> str:
        """Save file to local storage."""
        # Generate unique filename
        unique_name = self._generate_unique_filename(filename)

        # Create directory structure
        user_path = self._get_user_path(user_id)
        user_path.mkdir(parents=True, exist_ok=True)

        # Full path
        file_path = user_path / unique_name

        # Write file in chunks
        with open(file_path, "wb") as dest:
            shutil.copyfileobj(file, dest)

        # Return relative path
        return str(file_path.relative_to(self.base_path))

    async def get(self, path: str) -> Path | None:
        """Get local path to a file."""
        full_path = self.base_path / path
        if full_path.exists():
            return full_path
        return None

    async def delete(self, path: str) -> bool:
        """Delete a file."""
        full_path = self.base_path / path
        if full_path.exists():
            full_path.unlink()
            return True
        return False

    async def exists(self, path: str) -> bool:
        """Check if file exists."""
        return (self.base_path / path).exists()
```

---

## File Organization

Organizing by user and date provides:

```
storage/uploads/
├── 1/                    # user_id
│   ├── 2024/
│   │   ├── 01/
│   │   │   ├── 20240115_abc123def456.jpg
│   │   │   └── 20240116_xyz789uvw012.png
│   │   └── 02/
│   │       └── ...
│   └── ...
├── 2/
│   └── ...
└── ...
```

**Benefits:**
- **Scalability**: Thousands of files per directory (not millions)
- **Isolation**: Easy to delete all user data (GDPR)
- **Navigation**: Find files by date easily
- **Performance**: Filesystem handles directories better than huge flat directories

---

## S3 Storage Implementation (Future)

```python
import aioboto3
from botocore.config import Config

class S3StorageBackend(StorageBackend):
    """AWS S3 storage backend."""

    def __init__(
        self,
        bucket: str,
        region: str = "us-east-1",
        prefix: str = "uploads",
    ):
        self.bucket = bucket
        self.region = region
        self.prefix = prefix
        self.session = aioboto3.Session()

    def _get_key(self, user_id: int, filename: str) -> str:
        """Generate S3 key."""
        now = datetime.utcnow()
        unique = uuid.uuid4().hex[:16]
        ext = Path(filename).suffix.lower()
        return f"{self.prefix}/{user_id}/{now.year}/{now.month:02d}/{unique}{ext}"

    async def save(
        self,
        file: BinaryIO,
        filename: str,
        content_type: str,
        user_id: int,
    ) -> str:
        """Upload to S3."""
        key = self._get_key(user_id, filename)

        async with self.session.client("s3", region_name=self.region) as s3:
            await s3.upload_fileobj(
                file,
                self.bucket,
                key,
                ExtraArgs={"ContentType": content_type}
            )

        return key

    async def get(self, path: str) -> Path | None:
        """Download from S3 to temp file."""
        import tempfile

        async with self.session.client("s3", region_name=self.region) as s3:
            try:
                # Create temp file
                fd, local_path = tempfile.mkstemp()
                with os.fdopen(fd, 'wb') as f:
                    await s3.download_fileobj(self.bucket, path, f)
                return Path(local_path)
            except Exception:
                return None

    async def delete(self, path: str) -> bool:
        """Delete from S3."""
        async with self.session.client("s3", region_name=self.region) as s3:
            try:
                await s3.delete_object(Bucket=self.bucket, Key=path)
                return True
            except Exception:
                return False

    async def exists(self, path: str) -> bool:
        """Check if object exists in S3."""
        async with self.session.client("s3", region_name=self.region) as s3:
            try:
                await s3.head_object(Bucket=self.bucket, Key=path)
                return True
            except Exception:
                return False

    async def get_presigned_url(self, path: str, expires_in: int = 3600) -> str:
        """Generate a presigned URL for direct download."""
        async with self.session.client("s3", region_name=self.region) as s3:
            return await s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": path},
                ExpiresIn=expires_in
            )
```

---

## The High-Level Storage Service

```python
class StorageService:
    """
    High-level storage service.

    Wraps a storage backend with validation and utilities.
    """

    ALLOWED_IMAGE_TYPES = {
        "image/jpeg", "image/png", "image/gif",
        "image/webp", "image/bmp", "image/tiff",
    }
    MAX_FILE_SIZE = 50 * 1024 * 1024

    def __init__(self, backend: StorageBackend, settings: Settings | None = None):
        self.backend = backend
        self.settings = settings

        # Override max size from settings if available
        if settings and hasattr(settings.storage, 'max_file_size_bytes'):
            self.MAX_FILE_SIZE = settings.storage.max_file_size_bytes

    def validate_image(
        self,
        content_type: str,
        file_size: int,
    ) -> tuple[bool, str]:
        """Validate file type and size."""
        if content_type not in self.ALLOWED_IMAGE_TYPES:
            return False, f"Type '{content_type}' not allowed"
        if file_size > self.MAX_FILE_SIZE:
            return False, f"File too large"
        return True, ""

    async def save_file(
        self,
        file: BinaryIO,
        filename: str,
        content_type: str,
        user_id: int,
    ) -> str:
        """Save a validated file."""
        return await self.backend.save(file, filename, content_type, user_id)

    async def get_file_path(self, storage_path: str) -> Path | None:
        """Get path for serving."""
        return await self.backend.get(storage_path)

    async def delete_file(self, storage_path: str) -> bool:
        """Delete a file."""
        return await self.backend.delete(storage_path)

    def calculate_file_hash(self, file: BinaryIO) -> str:
        """Calculate SHA-256 for deduplication."""
        import hashlib
        hasher = hashlib.sha256()
        for chunk in iter(lambda: file.read(8192), b""):
            hasher.update(chunk)
        file.seek(0)
        return hasher.hexdigest()
```

---

## Initialization

```python
# Global instance
_storage_service: StorageService | None = None


def get_storage_service() -> StorageService:
    """Get the global storage service instance."""
    global _storage_service
    if _storage_service is None:
        raise RuntimeError("Storage not initialized. Call init_storage() first.")
    return _storage_service


def init_storage(settings: Settings) -> StorageService:
    """Initialize storage during application startup."""
    global _storage_service

    # Choose backend based on settings
    if settings.environment == "production" and hasattr(settings, 's3'):
        backend = S3StorageBackend(
            bucket=settings.s3.bucket,
            region=settings.s3.region,
        )
    else:
        backend = LocalStorageBackend(settings.storage.uploads_path)

    _storage_service = StorageService(backend, settings)
    return _storage_service
```

---

## Using the Storage Service

```python
# In app/main.py (startup)
from app.services.storage import init_storage

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_storage(settings)  # Initialize storage
    # ...


# In endpoints
from app.services.storage import get_storage_service

@router.post("/upload")
async def upload(file: UploadFile, user: CurrentUserDep):
    storage = get_storage_service()

    # Validate
    is_valid, error = storage.validate_image(file.content_type, file_size)
    if not is_valid:
        raise HTTPException(400, error)

    # Save
    content = await file.read()
    file_obj = io.BytesIO(content)
    path = await storage.save_file(file_obj, file.filename, file.content_type, user.id)

    return {"storage_path": path}
```

---

## File Deduplication

Save storage space by detecting duplicates:

```python
async def save_with_dedup(
    self,
    file: BinaryIO,
    filename: str,
    content_type: str,
    user_id: int,
    db: AsyncSession,
) -> str:
    """Save file with deduplication."""
    # Calculate hash
    file_hash = self.calculate_file_hash(file)

    # Check for existing file with same hash
    existing = await db.execute(
        select(Asset).where(Asset.file_hash == file_hash)
    )
    existing_asset = existing.scalar_one_or_none()

    if existing_asset:
        # File already exists, return existing path
        return existing_asset.storage_path

    # New file, save it
    return await self.backend.save(file, filename, content_type, user_id)
```

---

## Best Practices

### 1. Always Use the Abstraction

```python
# Don't do this:
with open(f"/storage/{user_id}/{filename}", "wb") as f:
    f.write(content)

# Do this:
storage = get_storage_service()
path = await storage.save_file(file, filename, content_type, user_id)
```

### 2. Store Relative Paths

```python
# In database:
storage_path = "1/2024/01/abc123.jpg"  # Relative

# Not:
storage_path = "/var/storage/uploads/1/2024/01/abc123.jpg"  # Absolute
```

### 3. Clean Up on Delete

```python
async def delete_asset(asset_id: int, db: AsyncSession):
    asset = await db.get(Asset, asset_id)

    # Delete file first
    storage = get_storage_service()
    await storage.delete_file(asset.storage_path)

    # Then delete database record
    await db.delete(asset)
```

### 4. Handle Missing Files

```python
async def download_asset(asset_id: int):
    asset = await db.get(Asset, asset_id)

    file_path = await storage.get_file_path(asset.storage_path)
    if not file_path:
        raise HTTPException(404, "File not found in storage")

    return FileResponse(file_path)
```

---

## Further Reading

- [boto3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)
- [aioboto3 for Async S3](https://aioboto3.readthedocs.io/)
- [MinIO - S3 Compatible Storage](https://min.io/)
