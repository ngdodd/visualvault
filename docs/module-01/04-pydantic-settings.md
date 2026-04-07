# Understanding Pydantic Settings

## What is Configuration Management?

Every application needs configuration - database URLs, API keys, feature flags, timeouts, etc. The challenge is managing these across different environments:

| Environment | Database | Debug | API Keys |
|-------------|----------|-------|----------|
| Development | localhost:5432 | true | test_key_123 |
| Staging | staging-db.example.com | false | staging_key_456 |
| Production | prod-db.example.com | false | prod_key_789 |

**Bad approaches:**
```python
# Hardcoded (never do this!)
DATABASE_URL = "postgresql://localhost:5432/mydb"

# Config file committed to git (secrets exposed!)
# config.json: {"api_key": "secret123"}
```

**Good approach:** Environment variables + validation = **Pydantic Settings**

---

## What is Pydantic Settings?

Pydantic Settings extends Pydantic to load and validate configuration from:
1. Environment variables
2. `.env` files
3. Default values
4. Secrets files (Docker secrets, etc.)

It provides:
- **Type validation**: Catch config errors at startup, not runtime
- **IDE support**: Autocomplete and type checking
- **Documentation**: Self-documenting configuration
- **Security**: Secrets stay in environment, not code

---

## Basic Usage

### Simple Settings Class

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "MyApp"
    debug: bool = False
    database_url: str

settings = Settings()
print(settings.app_name)  # "MyApp" (default)
print(settings.debug)     # False (default)
print(settings.database_url)  # From environment variable DATABASE_URL
```

**How it works:**
1. Pydantic looks for environment variable `DATABASE_URL`
2. If found, uses that value
3. If not found and no default, raises an error
4. Validates the type (converts "true" → `True` for bools)

### Environment Variable Mapping

By default, Pydantic converts field names to uppercase:

| Field | Environment Variable |
|-------|---------------------|
| `app_name` | `APP_NAME` |
| `debug` | `DEBUG` |
| `database_url` | `DATABASE_URL` |

---

## Our Configuration Structure

Let's examine `app/config.py`:

### Nested Settings

```python
class DatabaseSettings(BaseSettings):
    """Database configuration."""

    model_config = SettingsConfigDict(env_prefix="DB_")

    host: str = "localhost"
    port: int = 5432
    user: str = "visualvault"
    password: str = "visualvault"
    name: str = "visualvault"
```

**The `env_prefix`:** Adds a prefix to environment variable names.

| Field | Environment Variable |
|-------|---------------------|
| `host` | `DB_HOST` |
| `port` | `DB_PORT` |
| `password` | `DB_PASSWORD` |

This prevents naming collisions. Without prefixes, you might have `HOST` for database and `HOST` for Redis!

### Computed Properties

```python
class DatabaseSettings(BaseSettings):
    host: str = "localhost"
    port: int = 5432
    user: str = "visualvault"
    password: str = "visualvault"
    name: str = "visualvault"

    @computed_field
    @property
    def url(self) -> str:
        """Construct the database URL."""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"
```

**Why computed fields?**
- Derive values from other fields
- Avoid duplicating information
- Change `host` and `url` updates automatically

```python
settings = DatabaseSettings()
print(settings.url)
# postgresql+asyncpg://visualvault:visualvault@localhost:5432/visualvault

settings = DatabaseSettings(host="production-db.example.com")
print(settings.url)
# postgresql+asyncpg://visualvault:visualvault@production-db.example.com:5432/visualvault
```

### The Main Settings Class

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Simple fields
    app_name: str = "VisualVault"
    debug: bool = False
    environment: Literal["development", "staging", "production"] = "development"

    # Nested configurations
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
```

**Key options:**

| Option | Purpose |
|--------|---------|
| `env_file=".env"` | Load variables from .env file |
| `extra="ignore"` | Don't error on unknown env vars |
| `default_factory` | Create nested settings on demand |

### Literal Types for Validation

```python
environment: Literal["development", "staging", "production"] = "development"
```

Only these three values are allowed. If someone sets `ENVIRONMENT=prod`, they get a validation error:

```
pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings
environment
  Input should be 'development', 'staging' or 'production'
```

---

## The .env File

```bash
# .env
DEBUG=true
ENVIRONMENT=development

DB_HOST=localhost
DB_PORT=5432
DB_USER=visualvault
DB_PASSWORD=my-secret-password

REDIS_HOST=localhost

AUTH_SECRET_KEY=super-secret-key-change-in-production
```

**Important:** Never commit `.env` to git! Add it to `.gitignore`.

Instead, commit `.env.example` with placeholder values:

```bash
# .env.example
DEBUG=true
ENVIRONMENT=development

DB_HOST=localhost
DB_PASSWORD=change-me

AUTH_SECRET_KEY=generate-with-openssl-rand-hex-32
```

---

## The @lru_cache Pattern

```python
from functools import lru_cache

@lru_cache
def get_settings() -> Settings:
    """Create and cache settings instance."""
    return Settings()
```

**What is `@lru_cache`?**
- LRU = Least Recently Used
- Caches function return values
- Same arguments → same return value (cached)

**Why use it here?**
1. Settings should only load once at startup
2. Reading `.env` file is slow (disk I/O)
3. Multiple calls to `get_settings()` return the same instance

```python
# First call: reads .env, creates Settings
settings1 = get_settings()

# Second call: returns cached instance (instant)
settings2 = get_settings()

print(settings1 is settings2)  # True - same object!
```

---

## Using Settings in FastAPI

### As a Dependency

```python
from fastapi import Depends
from typing import Annotated
from app.config import Settings, get_settings

SettingsDep = Annotated[Settings, Depends(get_settings)]

@app.get("/info")
async def get_info(settings: SettingsDep):
    return {
        "app_name": settings.app_name,
        "environment": settings.environment,
        "debug": settings.debug,
    }
```

### In Lifespan Events

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # Use settings at startup
    if settings.debug:
        logger.setLevel(logging.DEBUG)

    settings.storage.uploads_path.mkdir(parents=True, exist_ok=True)

    yield
```

### Conditional Documentation

```python
def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        # Disable docs in production for security
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )
    return app
```

---

## Type Coercion

Pydantic automatically converts types:

```python
class Settings(BaseSettings):
    port: int = 8000
    debug: bool = False
    allowed_hosts: list[str] = []
```

```bash
# Environment
PORT=8080           # String "8080" → int 8080
DEBUG=true          # String "true" → bool True
DEBUG=1             # String "1" → bool True
DEBUG=yes           # String "yes" → bool True
ALLOWED_HOSTS=["localhost","127.0.0.1"]  # JSON string → list
```

**Boolean coercion:**
- Truthy: `true`, `True`, `1`, `yes`, `on`
- Falsy: `false`, `False`, `0`, `no`, `off`

---

## Validation Examples

### Path Validation

```python
from pathlib import Path

class StorageSettings(BaseSettings):
    base_path: Path = Path("storage")
    max_file_size_mb: int = Field(default=10, ge=1, le=100)
```

- `Path` type automatically converts strings to Path objects
- `ge=1, le=100` means value must be between 1 and 100

### URL Validation

```python
from pydantic import PostgresDsn, RedisDsn, HttpUrl

class Settings(BaseSettings):
    database_url: PostgresDsn
    redis_url: RedisDsn
    webhook_url: HttpUrl
```

Pydantic validates these are properly formatted URLs.

### Secret Strings

```python
from pydantic import SecretStr

class Settings(BaseSettings):
    api_key: SecretStr

settings = Settings()
print(settings.api_key)               # SecretStr('**********')
print(settings.api_key.get_secret_value())  # actual value
```

`SecretStr` prevents accidental logging of sensitive values.

---

## Testing with Different Settings

```python
# tests/conftest.py

def get_test_settings() -> Settings:
    return Settings(
        debug=True,
        environment="development",
        database=DatabaseSettings(
            name="visualvault_test",  # Use test database
        ),
    )

@pytest.fixture
def app():
    """Create app with test settings."""
    return create_app(get_test_settings())
```

---

## Settings Hierarchy

Pydantic Settings loads values in this order (later overrides earlier):

1. Default values in the class
2. `.env` file
3. Environment variables
4. Values passed to constructor

```python
class Settings(BaseSettings):
    debug: bool = False  # 1. Default

# .env file:
# DEBUG=true  # 2. .env file

# Shell:
# export DEBUG=false  # 3. Environment variable

# Code:
Settings(debug=True)  # 4. Constructor (highest priority)
```

---

## Best Practices

### 1. Always Provide Defaults for Non-Secrets

```python
# Good - has defaults
host: str = "localhost"
port: int = 5432

# Good - no default for secrets (forces explicit setting)
secret_key: str  # Will error if not set
```

### 2. Use Nested Settings for Organization

```python
# Instead of flat:
db_host: str
db_port: int
redis_host: str
redis_port: int

# Use nested:
database: DatabaseSettings
redis: RedisSettings
```

### 3. Document with Field Descriptions

```python
class Settings(BaseSettings):
    rate_limit: int = Field(
        default=100,
        description="Maximum requests per minute",
        ge=1,
        le=10000,
    )
```

### 4. Validate Early

```python
# At startup, not when first used
settings = get_settings()  # Validates immediately

# If validation fails, app won't start
# Better than crashing on first request!
```

---

## Common Issues

### Missing Required Field

```
pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings
database_url
  Field required
```

**Solution:** Set the environment variable or provide a default.

### Wrong Type

```
pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings
port
  Input should be a valid integer
```

**Solution:** Check the environment variable value.

### .env File Not Loading

```python
model_config = SettingsConfigDict(
    env_file=".env",  # Make sure this path is correct
    env_file_encoding="utf-8",
)
```

**Solution:** Ensure `.env` is in the working directory where you run the app.

---

## Further Reading

- [Pydantic Settings Documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [The Twelve-Factor App: Config](https://12factor.net/config)
- [Python-dotenv](https://github.com/theskumar/python-dotenv)
