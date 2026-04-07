# Module 2: Database & Authentication

## Overview

This module adds persistent data storage and user authentication to VisualVault. By the end, you'll have a fully functional user registration and login system with both JWT tokens and API keys.

## Learning Objectives

By completing this module, you will be able to:

1. **Configure async SQLAlchemy** - Modern SQLAlchemy 2.0 patterns with async/await
2. **Design database models** - Define tables, relationships, and constraints
3. **Manage schema migrations** - Use Alembic to version your database schema
4. **Implement password security** - Hash passwords with bcrypt
5. **Create JWT authentication** - Issue and verify access tokens
6. **Build API key authentication** - Alternative auth for programmatic access
7. **Protect endpoints** - Use FastAPI dependencies for authorization

---

## Prerequisites

- Completed Module 1
- Docker containers running (`docker-compose up -d`)
- Basic understanding of SQL databases

---

## Lesson Plan

### Part 1: Database Connection Setup (20 min)

**Concepts:**
- Async SQLAlchemy engine and session
- Connection pooling
- Session lifecycle in web requests

**Key Code:** `app/database.py`

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

def create_engine(settings: Settings):
    return create_async_engine(
        settings.database.url,
        echo=settings.database.echo,
        pool_size=settings.database.pool_size,
    )

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with _async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

**Key Takeaway:** The session is yielded to endpoints via dependency injection, automatically committed on success or rolled back on error.

**Read More:** [01-sqlalchemy-async.md](./01-sqlalchemy-async.md)

---

### Part 2: Model Design (25 min)

**Concepts:**
- SQLAlchemy 2.0 declarative models
- Type hints with `Mapped` and `mapped_column`
- Relationships and foreign keys
- Indexes and constraints

**Key Code:** `app/models/user.py`

```python
from sqlalchemy.orm import Mapped, mapped_column, relationship

class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)

    api_keys: Mapped[list["APIKey"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
```

**Key Takeaway:** SQLAlchemy 2.0 uses Python type hints for column definitions, making your models more readable and IDE-friendly.

**Read More:** [02-sqlalchemy-models.md](./02-sqlalchemy-models.md)

---

### Part 3: Alembic Migrations (20 min)

**Concepts:**
- Why migrations matter
- Alembic configuration
- Creating and running migrations
- Migration best practices

**Commands:**
```bash
# Create a new migration
alembic revision --autogenerate -m "Add users table"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history
```

**Key Takeaway:** Never modify the database schema directly in production. Always create a migration so changes are versioned and reproducible.

**Read More:** [03-alembic-migrations.md](./03-alembic-migrations.md)

---

### Part 4: Password Security (15 min)

**Concepts:**
- Why plain text passwords are dangerous
- Bcrypt hashing algorithm
- Salt and work factor
- Timing attack prevention

**Key Code:** `app/services/auth.py`

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)
```

**Key Takeaway:** Never store plain text passwords. Bcrypt automatically handles salting and provides configurable work factors to slow down brute force attacks.

**Read More:** [04-password-security.md](./04-password-security.md)

---

### Part 5: JWT Authentication (25 min)

**Concepts:**
- What is a JWT (JSON Web Token)
- Token structure (header, payload, signature)
- Access tokens vs refresh tokens
- Token expiration and validation

**Key Code:** `app/services/auth.py`

```python
from jose import jwt

def create_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        "type": "access",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def verify_access_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return int(payload.get("sub"))
    except JWTError:
        return None
```

**Key Takeaway:** JWTs are stateless - the server doesn't need to store session data. All information is encoded in the token itself.

**Read More:** [05-jwt-authentication.md](./05-jwt-authentication.md)

---

### Part 6: API Key Authentication (20 min)

**Concepts:**
- When to use API keys vs JWT
- Secure key generation
- Key storage (hash only!)
- Key rotation and revocation

**Key Code:** `app/services/auth.py`

```python
import secrets

def generate_api_key() -> str:
    prefix = "vv_"
    random_part = secrets.token_urlsafe(32)
    return f"{prefix}{random_part}"

async def create_api_key(user_id: int, data: APIKeyCreate) -> tuple[APIKey, str]:
    plain_key = generate_api_key()
    api_key = APIKey(
        user_id=user_id,
        key_prefix=plain_key[:11],
        key_hash=hash_password(plain_key),  # Store only the hash!
    )
    return api_key, plain_key  # Return plain key only once
```

**Key Takeaway:** Like passwords, never store API keys in plain text. The user sees the key once at creation; we store only the hash.

**Read More:** [06-api-keys.md](./06-api-keys.md)

---

### Part 7: Protected Endpoints (20 min)

**Concepts:**
- FastAPI security dependencies
- Bearer token extraction
- Current user dependency
- Optional authentication

**Key Code:** `app/api/v1/auth.py`

```python
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer

bearer_scheme = HTTPBearer(auto_error=False)

async def get_current_user(
    db: DbSessionDep,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> User:
    # Try JWT first, then API key
    if credentials:
        user = await verify_jwt(credentials.credentials)
        if user:
            return user

    if x_api_key:
        user = await verify_api_key(x_api_key)
        if user:
            return user

    raise HTTPException(status_code=401, detail="Not authenticated")

# Usage
@router.get("/me")
async def get_me(user: CurrentUserDep):
    return user
```

**Key Takeaway:** The `CurrentUserDep` dependency handles all authentication logic. Protected endpoints just declare it as a parameter.

---

## Hands-On Exercises

### Exercise 1: Register and Login

```bash
# Register a new user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"YourPass123"}'

# Login to get a token
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"YourPass123"}'

# Use the token
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer <your-token>"
```

### Exercise 2: Create and Use API Key

```bash
# Create an API key (requires auth)
curl -X POST http://localhost:8000/api/v1/auth/api-keys \
  -H "Authorization: Bearer <your-token>" \
  -H "Content-Type: application/json" \
  -d '{"name":"My Script"}'

# Use the API key
curl http://localhost:8000/api/v1/auth/me \
  -H "X-API-Key: vv_your_key_here"
```

### Exercise 3: Explore the Database

```bash
# Connect to PostgreSQL
docker-compose exec db psql -U visualvault

# List tables
\dt

# View users
SELECT id, email, is_active, created_at FROM users;

# View API keys
SELECT id, name, key_prefix, is_active FROM api_keys;
```

### Exercise 4: Create a Migration

```bash
# Add a field to User model (e.g., `avatar_url`)
# Then generate migration:
docker-compose exec api alembic revision --autogenerate -m "Add avatar_url to users"

# Apply it:
docker-compose exec api alembic upgrade head
```

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `app/database.py` | Engine, session maker, db dependency |
| `app/models/base.py` | Base class, naming conventions, mixins |
| `app/models/user.py` | User and APIKey models |
| `app/schemas/user.py` | Pydantic schemas for auth |
| `app/services/auth.py` | Password hashing, JWT, API keys |
| `app/api/v1/auth.py` | Auth endpoints and dependencies |
| `alembic/env.py` | Migration configuration |
| `alembic/versions/*.py` | Migration files |

---

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/v1/auth/register` | No | Create new user |
| POST | `/api/v1/auth/login` | No | Get JWT token |
| GET | `/api/v1/auth/me` | Yes | Get current user |
| POST | `/api/v1/auth/api-keys` | Yes | Create API key |
| GET | `/api/v1/auth/api-keys` | Yes | List API keys |
| DELETE | `/api/v1/auth/api-keys/{id}` | Yes | Revoke API key |

---

## Common Issues & Solutions

### "Password cannot be longer than 72 bytes"
**Cause:** Incompatible bcrypt version with passlib.
**Solution:** Pin bcrypt: `bcrypt>=4.0.0,<5.0.0`

### "Database not initialized"
**Cause:** `init_db()` not called at startup.
**Solution:** Ensure it's in the lifespan context manager.

### "Relation does not exist"
**Cause:** Migrations not run.
**Solution:** `docker-compose exec api alembic upgrade head`

### "Invalid token"
**Cause:** Token expired or wrong secret key.
**Solution:** Check token expiration; ensure `AUTH_SECRET_KEY` is consistent.

---

## Security Checklist

- [ ] Passwords hashed with bcrypt (never plain text)
- [ ] JWT secret key is strong and from environment
- [ ] API keys stored as hashes only
- [ ] Tokens have reasonable expiration times
- [ ] Failed logins don't reveal if email exists
- [ ] Password requirements enforced (length, complexity)

---

## What's Next: Module 3

In Module 3, we'll add:
- **File upload endpoints** with validation
- **Storage service** abstraction
- **Asset model** for tracking uploads
- **Image processing** utilities

---

## Additional Resources

- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/en/20/)
- [Alembic Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [JWT.io](https://jwt.io/) - JWT debugger
- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
