# Async SQLAlchemy: Database Connections

## What is SQLAlchemy?

SQLAlchemy is Python's most popular database toolkit. It provides:
- **ORM (Object-Relational Mapping)**: Work with database tables as Python classes
- **Core**: Lower-level SQL expression language
- **Connection pooling**: Efficient reuse of database connections

## Sync vs Async

Traditional (synchronous) database code blocks while waiting:

```python
# Sync - blocks the entire thread while waiting for database
def get_users():
    result = db.execute("SELECT * FROM users")  # Thread waits here
    return result.fetchall()
```

Async code can do other work while waiting:

```python
# Async - thread can handle other requests while waiting
async def get_users():
    result = await db.execute("SELECT * FROM users")  # Yields control
    return result.fetchall()
```

**Why async for web APIs?**
- Web servers handle many concurrent requests
- Most request time is spent waiting (database, external APIs)
- Async lets one thread handle many requests efficiently

---

## The Engine

The engine is the starting point for SQLAlchemy:

```python
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    "postgresql+asyncpg://user:pass@localhost/dbname",
    echo=True,           # Log SQL statements (dev only)
    pool_size=5,         # Keep 5 connections ready
    max_overflow=10,     # Allow 10 more under load
)
```

**Connection URL Format:**
```
dialect+driver://username:password@host:port/database

postgresql+asyncpg://...  # Async PostgreSQL
postgresql+psycopg2://... # Sync PostgreSQL
mysql+aiomysql://...      # Async MySQL
sqlite+aiosqlite://...    # Async SQLite
```

**The `asyncpg` driver:**
- High-performance async PostgreSQL driver
- Written in Cython for speed
- Required for async SQLAlchemy with PostgreSQL

---

## Connection Pooling

Creating database connections is expensive (~50-100ms). Connection pooling keeps connections ready:

```
┌─────────────────────────────────────────────────┐
│                 Connection Pool                  │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐       │
│  │Conn1│ │Conn2│ │Conn3│ │Conn4│ │Conn5│       │
│  └──┬──┘ └──┬──┘ └──┬──┘ └─────┘ └─────┘       │
│     │       │       │      idle    idle         │
└─────┼───────┼───────┼───────────────────────────┘
      │       │       │
      ▼       ▼       ▼
   Request Request Request
      1       2       3
```

**Pool settings:**
- `pool_size`: Connections to keep open (default: 5)
- `max_overflow`: Extra connections under heavy load (default: 10)
- `pool_timeout`: Seconds to wait for a connection (default: 30)
- `pool_recycle`: Recreate connections after N seconds (prevents stale connections)

```python
engine = create_async_engine(
    url,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,  # Recreate connections every 30 minutes
)
```

---

## The Session

A session represents a "conversation" with the database:

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# Create a session factory
async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Use the session
async with async_session_maker() as session:
    result = await session.execute(select(User))
    users = result.scalars().all()
```

**Session lifecycle:**
1. **Create**: Get a session from the pool
2. **Use**: Execute queries, add/modify objects
3. **Commit/Rollback**: Save changes or undo them
4. **Close**: Return connection to pool

---

## The Unit of Work Pattern

SQLAlchemy sessions track changes automatically:

```python
async with async_session_maker() as session:
    # Query a user
    user = await session.get(User, 1)

    # Modify it (session tracks this change)
    user.name = "New Name"

    # Add a new object (session tracks this too)
    new_user = User(email="new@example.com")
    session.add(new_user)

    # Commit saves ALL tracked changes in one transaction
    await session.commit()
```

**Benefits:**
- All changes succeed or fail together (atomicity)
- Efficient batching of changes
- Automatic dirty checking

---

## Our Database Setup

```python
# app/database.py

# Global references (initialized at startup)
_engine = None
_async_session_maker = None

def init_db(settings: Settings) -> None:
    """Initialize at application startup."""
    global _engine, _async_session_maker
    _engine = create_async_engine(settings.database.url)
    _async_session_maker = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

async def close_db() -> None:
    """Cleanup at application shutdown."""
    if _engine:
        await _engine.dispose()
```

**Why `expire_on_commit=False`?**

By default, SQLAlchemy "expires" all objects after commit, meaning accessing attributes would require another database query. In web APIs, we often want to return the object after saving it:

```python
# With expire_on_commit=True (default):
user = User(email="test@example.com")
session.add(user)
await session.commit()
print(user.email)  # ERROR! Would need to re-query

# With expire_on_commit=False:
await session.commit()
print(user.email)  # Works! Still has the value
```

---

## The Database Dependency

FastAPI dependency injection makes database access elegant:

```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session for each request."""
    async with _async_session_maker() as session:
        try:
            yield session         # Request handler runs here
            await session.commit()  # Auto-commit on success
        except Exception:
            await session.rollback()  # Auto-rollback on error
            raise

# Type alias for convenience
DbSessionDep = Annotated[AsyncSession, Depends(get_db)]
```

**Usage in endpoints:**

```python
@router.get("/users/{user_id}")
async def get_user(user_id: int, db: DbSessionDep):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    return user
```

**What happens:**
1. Request comes in
2. FastAPI calls `get_db()`, creating a session
3. Session is passed to your endpoint
4. Your code runs
5. If no exception: commit
6. If exception: rollback
7. Session returns to pool

---

## Common Queries

### Select

```python
from sqlalchemy import select

# Get all users
result = await db.execute(select(User))
users = result.scalars().all()

# Get one by ID
user = await db.get(User, 1)

# Filter
result = await db.execute(
    select(User).where(User.email == "test@example.com")
)
user = result.scalar_one_or_none()

# Multiple conditions
result = await db.execute(
    select(User)
    .where(User.is_active == True)
    .where(User.created_at > some_date)
    .order_by(User.created_at.desc())
    .limit(10)
)
```

### Insert

```python
# Single insert
user = User(email="new@example.com", hashed_password="...")
db.add(user)
await db.flush()  # Get the ID without committing
print(user.id)    # Now has the database-generated ID

# Bulk insert
users = [User(email=f"user{i}@example.com") for i in range(100)]
db.add_all(users)
await db.commit()
```

### Update

```python
# Update via object
user = await db.get(User, 1)
user.email = "updated@example.com"
await db.commit()

# Bulk update
from sqlalchemy import update
await db.execute(
    update(User)
    .where(User.is_active == False)
    .values(email=None)
)
await db.commit()
```

### Delete

```python
# Delete via object
user = await db.get(User, 1)
await db.delete(user)
await db.commit()

# Bulk delete
from sqlalchemy import delete
await db.execute(
    delete(User).where(User.is_active == False)
)
await db.commit()
```

---

## Handling Transactions

For operations that must succeed or fail together:

```python
async def transfer_funds(db: AsyncSession, from_id: int, to_id: int, amount: float):
    # All operations in this function share one transaction
    from_account = await db.get(Account, from_id)
    to_account = await db.get(Account, to_id)

    if from_account.balance < amount:
        raise ValueError("Insufficient funds")

    from_account.balance -= amount
    to_account.balance += amount

    # Commit happens in get_db() after this returns
    # If an error occurs, rollback happens automatically
```

For nested transactions (savepoints):

```python
async with db.begin_nested():
    # This part can be rolled back independently
    try:
        await do_risky_operation()
    except Exception:
        # Rollback only this nested transaction
        pass
# Outer transaction continues
```

---

## Best Practices

### 1. One Session Per Request
Don't share sessions between requests or store them globally.

### 2. Keep Sessions Short-Lived
Open session → do work → commit/rollback → close.

### 3. Use Dependency Injection
Let FastAPI manage session lifecycle via `Depends(get_db)`.

### 4. Handle Errors Gracefully
The `get_db` dependency handles rollback automatically.

### 5. Index Frequently Queried Columns
```python
email: Mapped[str] = mapped_column(String(255), index=True)
```

### 6. Use Async All the Way
Don't mix sync and async code. If you must call sync code:
```python
await asyncio.to_thread(sync_function, args)
```

---

## Further Reading

- [SQLAlchemy 2.0 Async Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [asyncpg Documentation](https://magicstack.github.io/asyncpg/)
- [Connection Pooling Explained](https://docs.sqlalchemy.org/en/20/core/pooling.html)
