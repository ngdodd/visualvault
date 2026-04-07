# JWT Authentication: Stateless Tokens

## What is a JWT?

**JWT** (JSON Web Token) is a compact, URL-safe way to represent claims between parties.

```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c
```

That long string contains:
1. **Header** - Algorithm and token type
2. **Payload** - The actual data (claims)
3. **Signature** - Verification that it hasn't been tampered with

---

## Why JWT for Web APIs?

### Traditional Session-Based Auth

```
┌──────────┐     1. Login         ┌──────────┐
│  Client  │ ──────────────────►  │  Server  │
│          │                      │          │
│          │  2. Session ID       │  Store   │
│          │ ◄──────────────────  │  Session │
│          │                      │  in DB   │
│          │  3. Request +        │          │
│          │     Session ID       │  Lookup  │
│          │ ──────────────────►  │  Session │
└──────────┘                      └──────────┘
```

**Problems:**
- Server must store session state (memory/database)
- Hard to scale (sessions don't share across servers)
- CORS complications with cookies

### JWT-Based Auth

```
┌──────────┐     1. Login         ┌──────────┐
│  Client  │ ──────────────────►  │  Server  │
│          │                      │          │
│  Store   │  2. JWT Token        │  No      │
│  Token   │ ◄──────────────────  │  State!  │
│          │                      │          │
│          │  3. Request + JWT    │  Verify  │
│          │ ──────────────────►  │  Token   │
└──────────┘                      └──────────┘
```

**Benefits:**
- **Stateless** - Server doesn't store sessions
- **Scalable** - Any server can verify the token
- **Mobile-friendly** - No cookies needed
- **Cross-domain** - Works across different origins

---

## JWT Structure Deep Dive

### 1. Header

```json
{
  "alg": "HS256",
  "typ": "JWT"
}
```

- **alg** - Signing algorithm (HS256 = HMAC-SHA256)
- **typ** - Token type (always "JWT")

### 2. Payload (Claims)

```json
{
  "sub": "123",
  "email": "user@example.com",
  "exp": 1704067200,
  "iat": 1704063600,
  "type": "access"
}
```

**Standard claims:**
| Claim | Name | Purpose |
|-------|------|---------|
| `sub` | Subject | User identifier |
| `exp` | Expiration | When token expires (Unix timestamp) |
| `iat` | Issued At | When token was created |
| `nbf` | Not Before | Token not valid before this time |
| `iss` | Issuer | Who created the token |
| `aud` | Audience | Who the token is for |

**Custom claims:**
- `type` - Token type (access, refresh)
- `roles` - User roles
- Any other data you need

### 3. Signature

```
HMACSHA256(
  base64UrlEncode(header) + "." + base64UrlEncode(payload),
  secret_key
)
```

The signature ensures the token hasn't been modified.

---

## How Tokens Are Verified

```
┌─────────────────────────────────────────────────────────┐
│                    JWT Token                             │
│  eyJhbG...  .  eyJzdWI...  .  SflKxw...                │
│   Header       Payload        Signature                  │
└─────────────────────────────────────────────────────────┘
                        ↓
        1. Split into parts
                        ↓
        2. Decode header and payload (Base64)
                        ↓
        3. Recreate signature using secret key
                        ↓
        4. Compare signatures
                        ↓
              ┌─────────────────┐
              │   Match?        │
              ├────────┬────────┤
              │  Yes   │   No   │
              │  ✓     │   ✗    │
              │ Valid  │ Reject │
              └────────┴────────┘
                        ↓
        5. Check expiration (exp claim)
                        ↓
        6. Return payload data
```

---

## Our Implementation

```python
# app/services/auth.py

from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError

SECRET_KEY = "your-secret-key"  # From settings in production!
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


def create_access_token(user_id: int) -> str:
    """Create a JWT access token for a user."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),      # Subject: user identifier
        "exp": expire,             # Expiration time
        "iat": datetime.now(timezone.utc),  # Issued at
        "type": "access",          # Token type
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_access_token(token: str) -> int | None:
    """Verify a JWT and return the user ID if valid."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # Check token type
        if payload.get("type") != "access":
            return None

        # Get user ID
        user_id = payload.get("sub")
        if user_id is None:
            return None

        return int(user_id)

    except JWTError:
        # Invalid signature, expired, malformed, etc.
        return None
```

---

## Access vs Refresh Tokens

### Access Token
- **Short-lived** (15-60 minutes)
- **Used for API requests**
- Sent in Authorization header
- If compromised, limited damage window

### Refresh Token
- **Long-lived** (days to weeks)
- **Used only to get new access tokens**
- Stored securely (httpOnly cookie or secure storage)
- Can be revoked server-side

```
┌──────────┐                              ┌──────────┐
│  Client  │  1. Login                    │  Server  │
│          │ ────────────────────────────►│          │
│          │                              │          │
│          │  2. Access + Refresh tokens  │          │
│          │ ◄────────────────────────────│          │
│          │                              │          │
│          │  3. API requests             │          │
│          │     (Access token)           │          │
│          │ ────────────────────────────►│          │
│          │                              │          │
│          │  4. Access token expires     │          │
│          │                              │          │
│          │  5. Refresh request          │          │
│          │     (Refresh token)          │          │
│          │ ────────────────────────────►│          │
│          │                              │          │
│          │  6. New access token         │          │
│          │ ◄────────────────────────────│          │
└──────────┘                              └──────────┘
```

---

## FastAPI Integration

### Bearer Token Extraction

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Auto-extracts "Bearer <token>" from Authorization header
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    db: DbSessionDep,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    """Dependency to get the authenticated user."""

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = verify_access_token(credentials.credentials)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return user


# Type alias for cleaner endpoints
CurrentUserDep = Annotated[User, Depends(get_current_user)]
```

### Using in Endpoints

```python
@router.get("/me")
async def get_me(user: CurrentUserDep) -> UserResponse:
    """Get the current user's profile."""
    return user


@router.get("/protected-data")
async def get_protected_data(user: CurrentUserDep):
    """Only authenticated users can access this."""
    return {"message": f"Hello, {user.email}!"}
```

---

## Token Expiration Strategies

### Short Expiration (Recommended)

```python
# Access token: 30 minutes
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Benefits:
# - Limited exposure if token is stolen
# - Forces regular re-authentication
# - Works well with refresh tokens
```

### Sliding Window

```python
# Check remaining time on each request
def should_refresh(payload: dict) -> bool:
    exp = payload.get("exp")
    remaining = exp - datetime.now(timezone.utc).timestamp()
    return remaining < 300  # Less than 5 minutes left
```

### Absolute Expiration

```python
# Token expires at a fixed time regardless of activity
# Good for sensitive operations
```

---

## Security Considerations

### 1. Keep Secrets Secret

```python
# BAD: Hardcoded secret
SECRET_KEY = "my-secret-key"

# GOOD: From environment
SECRET_KEY = settings.auth.secret_key  # Set via AUTH_SECRET_KEY env var
```

### 2. Use Strong Secrets

```bash
# Generate a secure secret
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Validate All Claims

```python
def verify_access_token(token: str) -> int | None:
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],  # Specify allowed algorithms!
        )

        # Check expiration (jose does this automatically)
        # Check token type
        if payload.get("type") != "access":
            return None

        # Check issuer if using multiple services
        # if payload.get("iss") != "visualvault":
        #     return None

        return int(payload.get("sub"))
    except JWTError:
        return None
```

### 4. Algorithm Confusion Attack

```python
# ALWAYS specify algorithms explicitly
# NEVER do this:
jwt.decode(token, SECRET_KEY)  # BAD: Accepts any algorithm

# ALWAYS do this:
jwt.decode(token, SECRET_KEY, algorithms=["HS256"])  # GOOD
```

### 5. Store Tokens Securely (Client Side)

| Storage | Security | Notes |
|---------|----------|-------|
| localStorage | Low | Vulnerable to XSS |
| sessionStorage | Low | Vulnerable to XSS |
| httpOnly Cookie | High | Immune to XSS, needs CSRF protection |
| Memory | High | Lost on refresh |

---

## Token Revocation

JWTs are stateless, so revoking them is tricky:

### Option 1: Short Expiration
Just wait for them to expire (simplest).

### Option 2: Token Blacklist
```python
# Store revoked tokens in Redis
revoked_tokens = set()  # Use Redis in production

def verify_access_token(token: str) -> int | None:
    if token in revoked_tokens:
        return None
    # ... normal verification
```

### Option 3: Token Version
```python
# Store version in user record
class User(Base):
    token_version: Mapped[int] = mapped_column(default=1)

# Include version in JWT
payload = {
    "sub": str(user_id),
    "version": user.token_version,
}

# On verify, check version matches
if payload.get("version") != user.token_version:
    return None  # Token invalidated

# To revoke all tokens: increment user.token_version
```

---

## Error Responses

Return consistent, secure error responses:

```python
# Always return 401 with WWW-Authenticate header
raise HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)
```

**Don't reveal:**
- Whether the token is expired vs invalid signature
- Whether the user exists
- Internal error details

---

## Testing JWT Authentication

```python
def test_create_and_verify_token():
    token = create_access_token(user_id=123)

    # Token is a string
    assert isinstance(token, str)

    # Can be verified
    user_id = verify_access_token(token)
    assert user_id == 123


def test_expired_token():
    # Create token that's already expired
    payload = {
        "sub": "123",
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        "type": "access",
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    # Should fail verification
    assert verify_access_token(token) is None


def test_invalid_signature():
    # Create token with wrong secret
    payload = {"sub": "123", "type": "access"}
    token = jwt.encode(payload, "wrong-secret", algorithm=ALGORITHM)

    # Should fail verification
    assert verify_access_token(token) is None


def test_protected_endpoint(client, auth_headers):
    # Without auth
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401

    # With auth
    response = client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
```

---

## Common Mistakes

### 1. Storing Sensitive Data in JWT

```python
# BAD: Password in token
payload = {"sub": "123", "password": "secret123"}

# GOOD: Only identifiers
payload = {"sub": "123"}
```

JWTs are encoded, not encrypted. Anyone can decode the payload.

### 2. Not Validating Expiration

```python
# BAD: Manual decode without expiration check
payload = jwt.decode(token, SECRET_KEY, options={"verify_exp": False})

# GOOD: Let the library check expiration
payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
```

### 3. Using Symmetric Keys in Distributed Systems

For microservices, consider asymmetric algorithms (RS256):
- Auth service signs with private key
- Other services verify with public key
- Private key stays in one place

---

## Debugging JWTs

Use [jwt.io](https://jwt.io/) to decode and inspect tokens:

1. Paste the token
2. See decoded header and payload
3. Verify signature (if you enter the secret)

**Never paste production tokens with real secrets into online tools!**

---

## Further Reading

- [JWT.io Introduction](https://jwt.io/introduction)
- [RFC 7519 - JSON Web Token](https://datatracker.ietf.org/doc/html/rfc7519)
- [OWASP JWT Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html)
- [python-jose Documentation](https://python-jose.readthedocs.io/)
