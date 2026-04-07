# Password Security: Protecting User Credentials

## Why Password Security Matters

A database breach exposing plain text passwords is catastrophic:

- **Users reuse passwords** - One breach compromises their accounts elsewhere
- **Legal liability** - GDPR, CCPA, and other regulations require protecting user data
- **Reputation damage** - Users lose trust in your service

**Never store plain text passwords. Ever.**

---

## How Password Hashing Works

```
Plain Password:    "MySecret123"
                        ↓
              Hash Function (bcrypt)
                        ↓
Hashed Password:   "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.QZe6s5x0mXwH.y"
```

**Key properties:**
- **One-way** - Cannot reverse the hash to get the password
- **Deterministic** - Same input always produces same output (with same salt)
- **Avalanche effect** - Tiny input change completely changes output

---

## Why Bcrypt?

Many hashing algorithms exist. Here's why we use bcrypt:

| Algorithm | Purpose | Good for Passwords? |
|-----------|---------|---------------------|
| MD5 | Checksums | ❌ Too fast, collision attacks |
| SHA-256 | Digital signatures | ❌ Too fast for passwords |
| bcrypt | Password hashing | ✅ Designed for this purpose |
| Argon2 | Password hashing | ✅ Newer alternative |

**Speed is the enemy!**

A fast hash lets attackers try billions of passwords per second. Bcrypt is intentionally slow (~100ms per hash), making brute force impractical.

---

## Understanding Bcrypt Output

```
$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.QZe6s5x0mXwH.y
│ │  │  └──────────────────────────────────────────────────────┘
│ │  │                          Hash + Salt
│ │  └── Work Factor (2^12 = 4096 iterations)
│ └── Algorithm version (2b = current)
└── Algorithm identifier ($)
```

**Components:**
- **Version** (`2b`): The bcrypt algorithm version
- **Work Factor** (`12`): How many iterations (2^12 = 4,096)
- **Salt + Hash** (rest): 22-char salt + 31-char hash

---

## Salt: Defeating Rainbow Tables

A **salt** is random data added before hashing:

```
Without salt:
"password123" → hash → "5f4dcc3b..."  (same for everyone)

With salt:
"password123" + "randomsalt1" → hash → "a1b2c3d4..."
"password123" + "randomsalt2" → hash → "x9y8z7w6..."
```

**Why salts matter:**
- **Rainbow tables** are precomputed hash databases
- Without salt, attackers can look up common password hashes
- With unique salts, each password must be cracked individually

**Bcrypt handles salting automatically!**

---

## Work Factor: Staying Ahead

The work factor controls how slow hashing is:

| Factor | Iterations | Time (approx) |
|--------|------------|---------------|
| 10 | 1,024 | ~100ms |
| 12 | 4,096 | ~250ms |
| 14 | 16,384 | ~1s |
| 16 | 65,536 | ~4s |

**Recommendations:**
- **Development**: 4 (fast tests)
- **Production**: 12 (current standard)
- **High security**: 14+ (banks, government)

As computers get faster, increase the work factor.

---

## Our Implementation

```python
# app/services/auth.py

from passlib.context import CryptContext

# Configure passlib with bcrypt
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",  # Automatically upgrade old hashes
)


def hash_password(password: str) -> str:
    """Hash a password for storage."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)
```

**Usage:**

```python
# At registration
hashed = hash_password("user_password")
# Store hashed in database

# At login
if verify_password(submitted_password, stored_hash):
    # Login successful
else:
    # Invalid password
```

---

## Timing Attack Prevention

A **timing attack** measures how long verification takes:

```python
# BAD: Early return reveals information
def verify_naive(password, hash):
    for i in range(len(password)):
        if password[i] != expected[i]:
            return False  # Fast fail leaks information
    return True
```

If "password1" fails faster than "password2", attackers know they're getting closer.

**Passlib handles this automatically** using constant-time comparison.

---

## Password Requirements

Enforce minimum security standards:

```python
# app/schemas/user.py

from pydantic import field_validator

class UserCreate(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain an uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain a lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain a digit")
        return v
```

**NIST Guidelines (2024):**
- Minimum 8 characters (12+ recommended)
- Check against common passwords list
- Don't require special characters (leads to "Password1!")
- Don't force regular password changes

---

## Don't Reveal User Existence

Login errors should be vague:

```python
# BAD: Reveals if email exists
if not user:
    raise HTTPException(400, "Email not found")
if not verify_password(password, user.hashed_password):
    raise HTTPException(400, "Wrong password")

# GOOD: Same message for both cases
if not user or not verify_password(password, user.hashed_password):
    raise HTTPException(400, "Invalid email or password")
```

---

## Password Reset Flow

Never send passwords via email. Use tokens:

```
1. User requests reset → Generate random token
2. Store token hash in database (with expiration)
3. Email link: /reset-password?token=abc123
4. User clicks link → Verify token, show password form
5. User submits new password → Hash and store
6. Invalidate the token
```

**Token security:**
- Use `secrets.token_urlsafe(32)` for generation
- Store only the hash of the token
- Expire tokens after 1 hour
- Single use only

---

## Common Vulnerabilities

### 1. Storing Plain Text
```python
# NEVER DO THIS
user.password = request.password
```

### 2. Using MD5/SHA for Passwords
```python
# DON'T DO THIS
import hashlib
hashed = hashlib.md5(password.encode()).hexdigest()
```

### 3. Hardcoded Salt
```python
# DON'T DO THIS
hashed = bcrypt.hash(password + "same_salt_for_everyone")
```

### 4. Weak Work Factor
```python
# DON'T DO THIS in production
pwd_context = CryptContext(schemes=["bcrypt"], bcrypt__rounds=4)
```

---

## Testing Password Hashing

```python
# tests/test_auth.py

def test_password_hashing():
    password = "SecurePass123"
    hashed = hash_password(password)

    # Hash is not the plain password
    assert hashed != password

    # Hash starts with bcrypt identifier
    assert hashed.startswith("$2b$")

    # Verification works
    assert verify_password(password, hashed)

    # Wrong password fails
    assert not verify_password("wrong", hashed)


def test_unique_hashes():
    """Same password produces different hashes (due to salt)."""
    password = "SecurePass123"
    hash1 = hash_password(password)
    hash2 = hash_password(password)

    # Different hashes
    assert hash1 != hash2

    # Both verify correctly
    assert verify_password(password, hash1)
    assert verify_password(password, hash2)
```

---

## Passlib Features

### Auto-Deprecation

```python
pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated="auto",
)

# Old bcrypt hash
old_hash = "$2b$12$..."

# Verify still works
if pwd_context.verify(password, old_hash):
    # Check if re-hash needed
    if pwd_context.needs_update(old_hash):
        new_hash = pwd_context.hash(password)
        # Update stored hash to argon2
```

### Custom Rounds

```python
# Development (fast)
pwd_context = CryptContext(
    schemes=["bcrypt"],
    bcrypt__rounds=4,
)

# Production (secure)
pwd_context = CryptContext(
    schemes=["bcrypt"],
    bcrypt__rounds=12,
)
```

---

## Best Practices Summary

1. **Use bcrypt or argon2** - Never MD5, SHA, or plain text
2. **Let the library handle salting** - Don't roll your own
3. **Use work factor 12+** in production
4. **Validate password strength** at registration
5. **Same error for wrong email/password** - Don't reveal user existence
6. **Use constant-time comparison** - Passlib does this automatically
7. **Never log passwords** - Even in development
8. **Test your hashing** - Ensure it works correctly

---

## Further Reading

- [OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
- [bcrypt Paper](https://www.usenix.org/legacy/events/usenix99/provos/provos.pdf)
- [NIST Digital Identity Guidelines](https://pages.nist.gov/800-63-3/)
- [Passlib Documentation](https://passlib.readthedocs.io/)
