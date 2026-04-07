# SQLAlchemy Models: Defining Your Data

## What is an ORM Model?

An ORM (Object-Relational Mapping) model is a Python class that represents a database table:

```python
# Python class
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255))

# Becomes SQL table
# CREATE TABLE users (
#     id SERIAL PRIMARY KEY,
#     email VARCHAR(255)
# )
```

Each instance of the class represents a row in the table.

---

## SQLAlchemy 2.0 Style

SQLAlchemy 2.0 introduced a new, cleaner syntax using Python type hints:

**Old style (1.x):**
```python
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False)
```

**New style (2.0):**
```python
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255))
```

**Benefits of 2.0 style:**
- Better IDE support (autocomplete, type checking)
- Clearer intent (types are explicit)
- Works with mypy and other type checkers

---

## The Declarative Base

All models inherit from a base class:

```python
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class User(Base):  # Inherits from Base
    __tablename__ = "users"
    ...
```

The base class:
- Tracks all models for migrations
- Provides shared configuration
- Holds the metadata (table definitions)

---

## Column Types

### Basic Types

```python
from sqlalchemy import String, Integer, Boolean, Float, DateTime, Text

class Example(Base):
    __tablename__ = "examples"

    # Integer types
    id: Mapped[int] = mapped_column(primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)

    # String types
    name: Mapped[str] = mapped_column(String(100))  # VARCHAR(100)
    description: Mapped[str] = mapped_column(Text)  # TEXT (unlimited)

    # Boolean
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Float/Decimal
    price: Mapped[float] = mapped_column(Float)

    # DateTime
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
```

### Nullable Columns

```python
# Required (NOT NULL)
email: Mapped[str] = mapped_column(String(255))

# Optional (NULL allowed)
nickname: Mapped[str | None] = mapped_column(String(100))
# or
nickname: Mapped[Optional[str]] = mapped_column(String(100))
```

The `Mapped[str | None]` type hint tells SQLAlchemy (and your IDE) that this column can be NULL.

### Default Values

```python
# Python default (set by application)
is_active: Mapped[bool] = mapped_column(default=True)

# Dynamic Python default
created_at: Mapped[datetime] = mapped_column(
    default=lambda: datetime.now(timezone.utc)
)

# Database default (set by database)
created_at: Mapped[datetime] = mapped_column(
    server_default=func.now()
)

# Update default (on UPDATE)
updated_at: Mapped[datetime] = mapped_column(
    onupdate=lambda: datetime.now(timezone.utc)
)
```

---

## Our User Model

```python
# app/models/user.py

class User(Base, TimestampMixin):
    __tablename__ = "users"

    # Primary key - auto-incrementing integer
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Email - unique, indexed for fast lookups
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    # Password - stored as hash, never plain text
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    # Profile info - optional
    full_name: Mapped[str | None] = mapped_column(String(255))

    # Account status flags
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationship to API keys
    api_keys: Mapped[list["APIKey"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
```

---

## Relationships

### One-to-Many

A user has many API keys:

```python
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)

    # One user has many API keys
    api_keys: Mapped[list["APIKey"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

class APIKey(Base):
    __tablename__ = "api_keys"
    id: Mapped[int] = mapped_column(primary_key=True)

    # Foreign key to user
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    # Many API keys belong to one user
    user: Mapped["User"] = relationship(back_populates="api_keys")
```

**Usage:**
```python
# Get user's API keys
user = await db.get(User, 1)
for key in user.api_keys:
    print(key.name)

# Get API key's user
api_key = await db.get(APIKey, 1)
print(api_key.user.email)
```

### Cascade Options

```python
api_keys: Mapped[list["APIKey"]] = relationship(
    cascade="all, delete-orphan",
)
```

| Cascade | Behavior |
|---------|----------|
| `save-update` | Add related objects when parent is added (default) |
| `merge` | Merge related objects when parent is merged |
| `delete` | Delete related objects when parent is deleted |
| `delete-orphan` | Delete objects removed from the collection |
| `all` | All of the above except delete-orphan |

### Loading Strategies

```python
# Lazy loading (default) - loads when accessed
api_keys: Mapped[list["APIKey"]] = relationship(lazy="select")

# Eager loading - loads with the parent query
api_keys: Mapped[list["APIKey"]] = relationship(lazy="selectin")

# Join loading - uses a JOIN
api_keys: Mapped[list["APIKey"]] = relationship(lazy="joined")
```

**In queries:**
```python
# Explicit eager loading
from sqlalchemy.orm import selectinload

result = await db.execute(
    select(User)
    .options(selectinload(User.api_keys))
    .where(User.id == 1)
)
user = result.scalar_one()
# user.api_keys already loaded, no extra query needed
```

---

## Constraints and Indexes

### Unique Constraint

```python
# Single column unique
email: Mapped[str] = mapped_column(unique=True)

# Multi-column unique (table level)
__table_args__ = (
    UniqueConstraint("tenant_id", "email", name="uq_tenant_email"),
)
```

### Indexes

```python
# Single column index
email: Mapped[str] = mapped_column(index=True)

# Composite index (table level)
__table_args__ = (
    Index("ix_user_active", "user_id", "is_active"),
)
```

### Foreign Keys

```python
user_id: Mapped[int] = mapped_column(
    ForeignKey("users.id", ondelete="CASCADE"),
    nullable=False,
)
```

**ondelete options:**
- `CASCADE`: Delete child when parent is deleted
- `SET NULL`: Set foreign key to NULL when parent is deleted
- `RESTRICT`: Prevent parent deletion if children exist
- `NO ACTION`: Same as RESTRICT (database dependent)

---

## Mixins

Reusable model components:

```python
# app/models/base.py

class TimestampMixin:
    """Adds created_at and updated_at to any model."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        onupdate=lambda: datetime.now(timezone.utc),
    )

# Usage
class User(Base, TimestampMixin):
    # Automatically has created_at and updated_at
    __tablename__ = "users"
    ...
```

---

## Naming Conventions

Consistent names for constraints help with migrations:

```python
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",           # Index
    "uq": "uq_%(table_name)s_%(column_0_name)s",  # Unique
    "ck": "ck_%(table_name)s_%(constraint_name)s", # Check
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",               # Primary key
}

class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
```

**Result:**
```sql
-- Primary key
CONSTRAINT pk_users PRIMARY KEY (id)

-- Foreign key
CONSTRAINT fk_api_keys_user_id_users FOREIGN KEY (user_id) REFERENCES users(id)

-- Index
CREATE INDEX ix_email ON users (email)
```

---

## Model Methods

Add helper methods to your models:

```python
class APIKey(Base):
    ...

    @property
    def is_expired(self) -> bool:
        """Check if the API key has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def scope_list(self) -> list[str]:
        """Get scopes as a list."""
        return [s.strip() for s in self.scopes.split(",")]

    def has_scope(self, scope: str) -> bool:
        """Check if this key has a specific scope."""
        return scope in self.scope_list

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<APIKey(id={self.id}, name={self.name})>"
```

---

## Best Practices

### 1. Use Meaningful Table Names
```python
__tablename__ = "user_api_keys"  # Clear, descriptive
__tablename__ = "uak"  # Too cryptic
```

### 2. Index Frequently Queried Columns
```python
email: Mapped[str] = mapped_column(index=True)  # Often used in WHERE
```

### 3. Use Foreign Key Constraints
They ensure data integrity at the database level.

### 4. Choose Appropriate Column Sizes
```python
name: Mapped[str] = mapped_column(String(100))  # Not String(10000)
```

### 5. Make Relationships Bidirectional
```python
# Both sides reference each other
user: Mapped["User"] = relationship(back_populates="api_keys")
api_keys: Mapped[list["APIKey"]] = relationship(back_populates="user")
```

### 6. Document with Comments
```python
scopes: Mapped[str] = mapped_column(
    Text,
    comment="Comma-separated list of allowed scopes",  # Stored in DB
)
```

---

## Further Reading

- [SQLAlchemy ORM Tutorial](https://docs.sqlalchemy.org/en/20/orm/quickstart.html)
- [Mapped Column API](https://docs.sqlalchemy.org/en/20/orm/mapped_attributes.html)
- [Relationship Configuration](https://docs.sqlalchemy.org/en/20/orm/relationships.html)
