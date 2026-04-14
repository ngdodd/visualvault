# Asset Model: Tracking Uploaded Files

## Why Track Assets?

The database needs to know about uploaded files:

- **Ownership**: Which user owns this file?
- **Metadata**: Original filename, size, dimensions
- **Location**: Where is the file stored?
- **Processing**: Has ML analysis completed?
- **Features**: What did ML extract (labels, colors, text)?

---

## Asset Lifecycle

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   PENDING   │ ──► │  PROCESSING  │ ──► │  COMPLETED  │
│             │     │              │     │             │
│  Uploaded,  │     │  ML pipeline │     │  Features   │
│  awaiting   │     │  analyzing   │     │  extracted  │
│  processing │     │  image       │     │             │
└─────────────┘     └──────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   FAILED    │
                    │             │
                    │  Error in   │
                    │  processing │
                    └─────────────┘
```

---

## The Asset Model

```python
# app/models/asset.py

from enum import Enum
from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class AssetStatus(str, Enum):
    """Processing status of an asset."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Asset(Base, TimestampMixin):
    """Represents an uploaded image asset."""

    __tablename__ = "assets"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Owner relationship
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # File information
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)

    # Storage location
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)

    # Image dimensions
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)

    # Processing status
    status: Mapped[str] = mapped_column(
        String(20),
        default=AssetStatus.PENDING.value,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # ML-extracted features (JSON strings)
    ml_labels: Mapped[str | None] = mapped_column(Text)
    ml_colors: Mapped[str | None] = mapped_column(Text)
    ml_text: Mapped[str | None] = mapped_column(Text)
    embedding_vector: Mapped[str | None] = mapped_column(Text)

    # Relationship
    user: Mapped["User"] = relationship(back_populates="assets")
```

---

## Field Explanations

### Identity & Ownership

| Field | Type | Purpose |
|-------|------|---------|
| `id` | int | Primary key, auto-incrementing |
| `user_id` | int | Foreign key to users table |

```python
# Get user's assets
assets = await db.execute(
    select(Asset).where(Asset.user_id == user.id)
)
```

### File Information

| Field | Type | Purpose |
|-------|------|---------|
| `filename` | str | Generated safe filename |
| `original_filename` | str | User's original filename |
| `content_type` | str | MIME type (image/jpeg) |
| `file_size` | int | Size in bytes |

```python
asset = Asset(
    filename="20240115_abc123.jpg",  # Safe, unique
    original_filename="My Vacation Photo.jpg",  # User's name
    content_type="image/jpeg",
    file_size=1024000,  # ~1MB
)
```

### Storage Location

| Field | Type | Purpose |
|-------|------|---------|
| `storage_path` | str | Relative path in storage |

```python
# Stored as relative path
storage_path = "1/2024/01/20240115_abc123.jpg"

# Full path resolved at runtime
full_path = settings.storage.uploads_path / storage_path
```

### Dimensions

| Field | Type | Purpose |
|-------|------|---------|
| `width` | int | Image width in pixels |
| `height` | int | Image height in pixels |

```python
# Set during upload
from app.utils.image import get_image_dimensions

dimensions = get_image_dimensions(file_obj)
if dimensions:
    asset.width, asset.height = dimensions
```

### Processing Status

| Field | Type | Purpose |
|-------|------|---------|
| `status` | str | Current processing state |
| `error_message` | str | Error details if failed |
| `processed_at` | datetime | When processing completed |

```python
# Update status in worker
asset.status = AssetStatus.PROCESSING.value

# On success
asset.status = AssetStatus.COMPLETED.value
asset.processed_at = datetime.now(timezone.utc)

# On failure
asset.status = AssetStatus.FAILED.value
asset.error_message = str(exception)
```

### ML Features

| Field | Type | Purpose |
|-------|------|---------|
| `ml_labels` | str | JSON array of detected labels |
| `ml_colors` | str | JSON array of dominant colors |
| `ml_text` | str | OCR extracted text |
| `embedding_vector` | str | JSON array of floats (512D) |

```python
import json

# Store labels
asset.ml_labels = json.dumps(["dog", "outdoor", "sunny"])

# Store colors
asset.ml_colors = json.dumps([
    {"hex": "#3498db", "percentage": 45.2},
    {"hex": "#2ecc71", "percentage": 30.1},
])

# Store embedding
asset.embedding_vector = json.dumps(embedding.tolist())
```

---

## Model Properties

```python
class Asset(Base, TimestampMixin):
    # ... fields ...

    @property
    def is_image(self) -> bool:
        """Check if asset is an image."""
        return self.content_type.startswith("image/")

    @property
    def is_processed(self) -> bool:
        """Check if processing is complete."""
        return self.status == AssetStatus.COMPLETED.value

    @property
    def dimensions(self) -> tuple[int, int] | None:
        """Get dimensions as tuple."""
        if self.width and self.height:
            return (self.width, self.height)
        return None

    @property
    def labels(self) -> list[str]:
        """Parse labels from JSON."""
        if self.ml_labels:
            try:
                return json.loads(self.ml_labels)
            except json.JSONDecodeError:
                pass
        return []

    def __repr__(self) -> str:
        return f"<Asset(id={self.id}, filename={self.original_filename})>"
```

---

## Indexes for Performance

```python
class Asset(Base, TimestampMixin):
    __tablename__ = "assets"

    # Column-level indexes
    user_id: Mapped[int] = mapped_column(..., index=True)
    status: Mapped[str] = mapped_column(..., index=True)

    # Composite indexes for common queries
    __table_args__ = (
        Index("ix_assets_user_status", "user_id", "status"),
        Index("ix_assets_user_created", "user_id", "created_at"),
    )
```

### Why These Indexes?

```python
# Find user's pending assets (uses ix_assets_user_status)
select(Asset).where(
    Asset.user_id == user_id,
    Asset.status == "pending"
)

# List user's recent assets (uses ix_assets_user_created)
select(Asset).where(
    Asset.user_id == user_id
).order_by(Asset.created_at.desc())
```

---

## The User Relationship

```python
# app/models/user.py

class User(Base, TimestampMixin):
    __tablename__ = "users"

    # ... user fields ...

    # Relationship to assets
    assets: Mapped[list["Asset"]] = relationship(
        "Asset",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",  # Lazy load (could be many assets)
    )
```

```python
# Usage
user = await db.get(User, user_id)

# Lazy load assets (triggers query)
for asset in user.assets:
    print(asset.filename)

# Or eager load
from sqlalchemy.orm import selectinload

result = await db.execute(
    select(User)
    .options(selectinload(User.assets))
    .where(User.id == user_id)
)
user = result.scalar_one()
# Assets already loaded, no extra query
```

---

## Common Queries

### Create Asset

```python
asset = Asset(
    user_id=user.id,
    filename="20240115_abc123.jpg",
    original_filename="photo.jpg",
    content_type="image/jpeg",
    file_size=1024000,
    storage_path="1/2024/01/20240115_abc123.jpg",
    width=1920,
    height=1080,
    status=AssetStatus.PENDING.value,
)
db.add(asset)
await db.flush()  # Get ID
```

### Get Asset by ID

```python
asset = await db.get(Asset, asset_id)
if not asset or asset.user_id != user.id:
    raise HTTPException(404, "Asset not found")
```

### List User's Assets

```python
result = await db.execute(
    select(Asset)
    .where(Asset.user_id == user.id)
    .order_by(Asset.created_at.desc())
    .offset(offset)
    .limit(limit)
)
assets = result.scalars().all()
```

### Filter by Status

```python
result = await db.execute(
    select(Asset)
    .where(Asset.user_id == user.id)
    .where(Asset.status == AssetStatus.PENDING.value)
)
pending_assets = result.scalars().all()
```

### Count Assets

```python
from sqlalchemy import func

result = await db.execute(
    select(func.count())
    .select_from(Asset)
    .where(Asset.user_id == user.id)
)
total = result.scalar()
```

### Update Status

```python
asset = await db.get(Asset, asset_id)
asset.status = AssetStatus.COMPLETED.value
asset.processed_at = datetime.now(timezone.utc)
asset.ml_labels = json.dumps(["dog", "outdoor"])
await db.commit()
```

### Delete Asset

```python
asset = await db.get(Asset, asset_id)

# Delete file from storage first
storage = get_storage_service()
await storage.delete_file(asset.storage_path)

# Then delete database record
await db.delete(asset)
await db.commit()
```

---

## The Migration

```python
# alembic/versions/002_create_assets_table.py

def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ml_labels", sa.Text(), nullable=True),
        sa.Column("ml_colors", sa.Text(), nullable=True),
        sa.Column("ml_text", sa.Text(), nullable=True),
        sa.Column("embedding_vector", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_assets"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_assets_user_id_users",
            ondelete="CASCADE",
        ),
    )

    op.create_index("ix_assets_user_id", "assets", ["user_id"])
    op.create_index("ix_assets_status", "assets", ["status"])
    op.create_index("ix_assets_user_status", "assets", ["user_id", "status"])
    op.create_index("ix_assets_user_created", "assets", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_assets_user_created", "assets")
    op.drop_index("ix_assets_user_status", "assets")
    op.drop_index("ix_assets_status", "assets")
    op.drop_index("ix_assets_user_id", "assets")
    op.drop_table("assets")
```

---

## Pydantic Schemas

```python
# app/schemas/asset.py

class AssetResponse(BaseModel):
    """Response schema for assets."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    original_filename: str
    content_type: str
    file_size: int
    width: int | None = None
    height: int | None = None
    status: str
    created_at: datetime
    processed_at: datetime | None = None
    url: str | None = None


class AssetDetail(AssetResponse):
    """Detailed response with ML features."""
    ml_labels: list[str] | None = None
    ml_colors: list[dict] | None = None
    ml_text: str | None = None
    error_message: str | None = None
```

---

## Best Practices

### 1. Always Check Ownership

```python
asset = await db.get(Asset, asset_id)
if not asset or asset.user_id != current_user.id:
    raise HTTPException(404, "Asset not found")
```

### 2. Use Cascade Delete

```python
# When user is deleted, their assets are too
user_id: Mapped[int] = mapped_column(
    ForeignKey("users.id", ondelete="CASCADE")
)
```

### 3. Store Relative Paths

```python
# Good: Relative to storage root
storage_path = "1/2024/01/abc123.jpg"

# Bad: Absolute path (hard to migrate)
storage_path = "/var/storage/uploads/1/2024/01/abc123.jpg"
```

### 4. Keep Original Filename

```python
# Users want to download with original name
original_filename = "My Vacation Photo.jpg"

# But store with safe, unique name
filename = "20240115_abc123def456.jpg"
```

---

## Further Reading

- [SQLAlchemy Relationships](https://docs.sqlalchemy.org/en/20/orm/relationships.html)
- [SQLAlchemy Indexes](https://docs.sqlalchemy.org/en/20/core/constraints.html#indexes)
- [Pydantic ORM Mode](https://docs.pydantic.dev/latest/concepts/models/#arbitrary-class-instances)
