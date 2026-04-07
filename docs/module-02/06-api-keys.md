# API Key Authentication: Programmatic Access

## When to Use API Keys vs JWT

| Use Case | JWT | API Key |
|----------|-----|---------|
| Interactive login (browser) | ✅ | ❌ |
| Mobile app authentication | ✅ | ❌ |
| Server-to-server API calls | ❌ | ✅ |
| CLI tools and scripts | ❌ | ✅ |
| Third-party integrations | ❌ | ✅ |
| Webhook callbacks | ❌ | ✅ |

**JWT** - Short-lived, tied to user session, good for interactive use
**API Key** - Long-lived, for programmatic access, can be scoped and revoked

---

## API Key Design

### Format

```
vv_sk_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
│  │  └─────────────────────────────────┘
│  │              Random part (32 chars)
│  └── Key type (sk = secret key)
└── Prefix (identifies your service)
```

**Benefits of prefixes:**
- Users can identify which service the key is for
- Accidentally exposed keys can be traced back
- GitHub secret scanning can detect them

### What We Store

```
┌───────────────────────────────────────────────────────┐
│                    Database                            │
│  ┌─────────┬────────────┬──────────────────────────┐  │
│  │ user_id │ key_prefix │ key_hash                 │  │
│  ├─────────┼────────────┼──────────────────────────┤  │
│  │ 1       │ vv_sk_a1b2 │ $2b$12$LQv3c1yq...      │  │
│  │ 1       │ vv_sk_x9y8 │ $2b$12$XYZ123ab...      │  │
│  └─────────┴────────────┴──────────────────────────┘  │
│                                                        │
│  We store ONLY the hash, never the full key!          │
└───────────────────────────────────────────────────────┘
```

**Like passwords, we never store the plain text API key.**

---

## Key Generation

```python
import secrets

def generate_api_key() -> str:
    """Generate a secure, prefixed API key."""
    prefix = "vv_sk_"
    # 32 bytes = 256 bits of randomness
    random_part = secrets.token_urlsafe(32)
    return f"{prefix}{random_part}"

# Example output: vv_sk_a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8s9T0
```

**Why `secrets.token_urlsafe`?**
- Cryptographically secure random
- URL-safe characters (A-Z, a-z, 0-9, -, _)
- No ambiguous characters (0 vs O, l vs 1)

---

## Our Implementation

### APIKey Model

```python
# app/models/user.py

class APIKey(Base, TimestampMixin):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))  # User-friendly name
    key_prefix: Mapped[str] = mapped_column(String(12))  # For identification
    key_hash: Mapped[str] = mapped_column(String(255))  # Hashed key
    is_active: Mapped[bool] = mapped_column(default=True)
    scopes: Mapped[str] = mapped_column(Text, default="")  # Comma-separated
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationship
    user: Mapped["User"] = relationship(back_populates="api_keys")

    @property
    def is_expired(self) -> bool:
        """Check if key has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at
```

### Creating API Keys

```python
# app/services/auth.py

async def create_api_key(
    db: AsyncSession,
    user_id: int,
    name: str,
    scopes: list[str] | None = None,
    expires_in_days: int | None = None,
) -> tuple[APIKey, str]:
    """
    Create a new API key for a user.

    Returns (APIKey model, plain_key)
    The plain key is returned ONLY ONCE - we don't store it!
    """
    # Generate the key
    plain_key = generate_api_key()

    # Calculate expiration
    expires_at = None
    if expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

    # Create the database record
    api_key = APIKey(
        user_id=user_id,
        name=name,
        key_prefix=plain_key[:11],  # Store prefix for identification
        key_hash=hash_password(plain_key),  # Hash like a password!
        scopes=",".join(scopes) if scopes else "",
        expires_at=expires_at,
    )

    db.add(api_key)
    await db.flush()

    return api_key, plain_key  # Return plain key only this once!
```

### Verifying API Keys

```python
async def verify_api_key(db: AsyncSession, plain_key: str) -> User | None:
    """
    Verify an API key and return the associated user.

    This is slower than JWT verification because we must:
    1. Query the database
    2. Verify the hash (bcrypt is intentionally slow)
    """
    # Extract prefix to narrow down the search
    prefix = plain_key[:11]

    # Find keys with matching prefix
    result = await db.execute(
        select(APIKey)
        .where(APIKey.key_prefix == prefix)
        .where(APIKey.is_active == True)
        .options(selectinload(APIKey.user))
    )
    api_keys = result.scalars().all()

    # Check each potential match
    for api_key in api_keys:
        if verify_password(plain_key, api_key.key_hash):
            # Found a match!
            if api_key.is_expired:
                return None
            if not api_key.user.is_active:
                return None
            return api_key.user

    return None
```

---

## Scopes: Fine-Grained Permissions

Not all API keys need full access:

```python
# Available scopes
SCOPES = {
    "read:assets": "Read asset information",
    "write:assets": "Upload and modify assets",
    "delete:assets": "Delete assets",
    "read:profile": "Read user profile",
    "write:profile": "Modify user profile",
}

# Create a read-only key
key, plain = await create_api_key(
    db, user_id=1, name="Analytics Script",
    scopes=["read:assets", "read:profile"]
)

# Create a full-access key
key, plain = await create_api_key(
    db, user_id=1, name="Admin Tool",
    scopes=list(SCOPES.keys())
)
```

### Checking Scopes in Endpoints

```python
def require_scope(scope: str):
    """Dependency that requires a specific scope."""
    async def check_scope(
        user: CurrentUserDep,
        api_key: APIKey | None = Depends(get_api_key),
    ):
        # JWT users have all scopes
        if api_key is None:
            return user

        # API key users need the specific scope
        if scope not in api_key.scope_list:
            raise HTTPException(
                status_code=403,
                detail=f"API key missing required scope: {scope}"
            )
        return user

    return check_scope


# Usage
@router.delete("/assets/{asset_id}")
async def delete_asset(
    asset_id: int,
    user: Annotated[User, Depends(require_scope("delete:assets"))],
):
    # Only keys with delete:assets scope can reach here
    ...
```

---

## API Key Endpoints

### Create Key

```python
@router.post("/api-keys", response_model=APIKeyCreated)
async def create_api_key_endpoint(
    data: APIKeyCreate,
    user: CurrentUserDep,
    db: DbSessionDep,
):
    """Create a new API key. Returns the key ONLY ONCE."""
    api_key, plain_key = await auth_service.create_api_key(
        db, user.id, data.name, data.scopes
    )
    return APIKeyCreated(
        id=api_key.id,
        name=api_key.name,
        key=plain_key,  # Only time the user sees this!
        scopes=api_key.scope_list,
        created_at=api_key.created_at,
    )
```

### List Keys

```python
@router.get("/api-keys", response_model=list[APIKeyInfo])
async def list_api_keys(user: CurrentUserDep, db: DbSessionDep):
    """List all API keys for the current user."""
    result = await db.execute(
        select(APIKey)
        .where(APIKey.user_id == user.id)
        .where(APIKey.is_active == True)
    )
    return result.scalars().all()
```

### Revoke Key

```python
@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: int,
    user: CurrentUserDep,
    db: DbSessionDep,
):
    """Revoke (deactivate) an API key."""
    result = await db.execute(
        select(APIKey)
        .where(APIKey.id == key_id)
        .where(APIKey.user_id == user.id)
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(404, "API key not found")

    api_key.is_active = False
    return {"message": "API key revoked"}
```

---

## Client Usage

### In HTTP Headers

```bash
# Recommended: X-API-Key header
curl https://api.example.com/assets \
  -H "X-API-Key: vv_sk_a1b2c3d4..."

# Alternative: Authorization header (Bearer)
curl https://api.example.com/assets \
  -H "Authorization: Bearer vv_sk_a1b2c3d4..."
```

### In Python

```python
import httpx

API_KEY = "vv_sk_a1b2c3d4..."

client = httpx.Client(
    base_url="https://api.example.com",
    headers={"X-API-Key": API_KEY}
)

response = client.get("/assets")
```

### In JavaScript

```javascript
const API_KEY = "vv_sk_a1b2c3d4...";

fetch("https://api.example.com/assets", {
    headers: {
        "X-API-Key": API_KEY
    }
})
```

---

## FastAPI Integration

```python
from fastapi import Header, HTTPException

async def get_current_user(
    db: DbSessionDep,
    # JWT from Authorization header
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    # API key from X-API-Key header
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> User:
    """
    Authenticate via JWT or API key.
    JWT is checked first, then API key.
    """
    # Try JWT
    if credentials:
        user_id = verify_access_token(credentials.credentials)
        if user_id:
            user = await db.get(User, user_id)
            if user and user.is_active:
                return user

    # Try API key
    if x_api_key:
        user = await verify_api_key(db, x_api_key)
        if user:
            return user

    raise HTTPException(
        status_code=401,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
```

---

## Security Best Practices

### 1. Show Key Only Once

```python
# Response after creation
{
    "id": 1,
    "name": "My Script",
    "key": "vv_sk_a1b2c3...",  # Only time user sees this!
    "message": "Store this key securely. You won't see it again."
}

# Subsequent responses
{
    "id": 1,
    "name": "My Script",
    "key_prefix": "vv_sk_a1b2",  # Just the prefix
    "created_at": "2024-01-15T10:00:00Z"
}
```

### 2. Rate Limit by Key

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

def get_rate_limit_key(request: Request) -> str:
    """Rate limit by API key if present, otherwise by IP."""
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return f"apikey:{api_key[:11]}"  # Use prefix
    return f"ip:{get_remote_address(request)}"

limiter = Limiter(key_func=get_rate_limit_key)
```

### 3. Audit Key Usage

```python
class APIKeyUsage(Base):
    __tablename__ = "api_key_usage"

    id: Mapped[int] = mapped_column(primary_key=True)
    api_key_id: Mapped[int] = mapped_column(ForeignKey("api_keys.id"))
    endpoint: Mapped[str] = mapped_column(String(255))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ip_address: Mapped[str] = mapped_column(String(45))
```

### 4. Support Key Rotation

```python
# User creates new key before revoking old one
# 1. Create new key
# 2. Update applications to use new key
# 3. Revoke old key

# Optionally, allow brief overlap period
@router.post("/api-keys/{key_id}/rotate")
async def rotate_api_key(key_id: int, user: CurrentUserDep, db: DbSessionDep):
    """Create new key and schedule old key for deletion."""
    old_key = await db.get(APIKey, key_id)
    if not old_key or old_key.user_id != user.id:
        raise HTTPException(404)

    # Create new key with same settings
    new_key, plain_key = await create_api_key(
        db, user.id, f"{old_key.name} (rotated)",
        scopes=old_key.scope_list
    )

    # Schedule old key for deactivation (e.g., 24 hours)
    old_key.expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

    return {"new_key": plain_key, "old_key_expires": old_key.expires_at}
```

---

## Common Mistakes

### 1. Storing Plain Text Keys

```python
# BAD: Storing the actual key
api_key = APIKey(key=plain_key)  # NO!

# GOOD: Store only the hash
api_key = APIKey(key_hash=hash_password(plain_key))
```

### 2. No Prefix/Identification

```python
# BAD: Can't identify the key in logs/alerts
key = secrets.token_urlsafe(32)

# GOOD: Prefixed for identification
key = f"vv_sk_{secrets.token_urlsafe(32)}"
```

### 3. No Expiration Option

```python
# BAD: Keys live forever
api_key = APIKey(user_id=user_id, key_hash=hash)

# GOOD: Optional expiration
api_key = APIKey(
    user_id=user_id,
    key_hash=hash,
    expires_at=datetime.now() + timedelta(days=90)
)
```

### 4. All-or-Nothing Permissions

```python
# BAD: Key has full access
api_key = APIKey(user_id=user_id, key_hash=hash)

# GOOD: Scoped permissions
api_key = APIKey(
    user_id=user_id,
    key_hash=hash,
    scopes="read:assets,read:profile"
)
```

---

## Testing API Keys

```python
async def test_create_api_key(client, auth_headers, db):
    response = client.post(
        "/api/v1/auth/api-keys",
        headers=auth_headers,
        json={"name": "Test Key"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "key" in data
    assert data["key"].startswith("vv_sk_")


async def test_use_api_key(client, db):
    # Create key via service
    api_key, plain_key = await create_api_key(db, user_id=1, name="Test")
    await db.commit()

    # Use it
    response = client.get(
        "/api/v1/auth/me",
        headers={"X-API-Key": plain_key}
    )
    assert response.status_code == 200


async def test_revoked_key(client, db):
    # Create and revoke
    api_key, plain_key = await create_api_key(db, user_id=1, name="Test")
    api_key.is_active = False
    await db.commit()

    # Should fail
    response = client.get(
        "/api/v1/auth/me",
        headers={"X-API-Key": plain_key}
    )
    assert response.status_code == 401
```

---

## Summary

| Aspect | Implementation |
|--------|----------------|
| Generation | `secrets.token_urlsafe(32)` with prefix |
| Storage | Hash with bcrypt, never plain text |
| Identification | Store prefix for lookup |
| Verification | Query by prefix, verify hash |
| Permissions | Scope-based access control |
| Lifecycle | Create once, show once, revoke when done |

---

## Further Reading

- [OWASP API Security - API Keys](https://owasp.org/API-Security/)
- [GitHub Token Formats](https://github.blog/2021-04-05-behind-githubs-new-authentication-token-formats/)
- [Stripe API Key Design](https://stripe.com/docs/keys)
