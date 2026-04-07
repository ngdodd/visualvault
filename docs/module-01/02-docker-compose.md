# Understanding Docker Compose

## What is Docker Compose?

Docker Compose is a tool for defining and running **multi-container applications**. Instead of running multiple `docker run` commands with complex options, you define your entire stack in a single YAML file.

**The Problem It Solves:**

Imagine starting our VisualVault application manually:

```bash
# Start PostgreSQL
docker run -d --name db \
  -e POSTGRES_USER=visualvault \
  -e POSTGRES_PASSWORD=visualvault \
  -v postgres_data:/var/lib/postgresql/data \
  postgres:15-alpine

# Start Redis
docker run -d --name redis \
  -v redis_data:/data \
  redis:7-alpine

# Start the API (needs to know about db and redis)
docker run -d --name api \
  -p 8000:8000 \
  -e DB_HOST=db \
  -e REDIS_HOST=redis \
  --link db --link redis \
  visualvault:dev

# Start the worker
docker run -d --name worker \
  -e DB_HOST=db \
  -e REDIS_HOST=redis \
  --link db --link redis \
  visualvault:dev celery -A app.workers.celery_app worker
```

**With Docker Compose:**

```bash
docker-compose up -d
```

One command starts everything, properly configured and connected.

---

## The docker-compose.yml File

Let's walk through our `docker-compose.yml` section by section:

### File Version and Services

```yaml
services:
  api:
    ...
  worker:
    ...
  db:
    ...
  redis:
    ...
```

The file defines **services** - each service becomes one or more containers. Service names (`api`, `db`, etc.) become hostnames on the internal Docker network.

---

### The API Service

```yaml
api:
  build:
    context: .
    target: development
  ports:
    - "8000:8000"
  volumes:
    - ./app:/app/app:ro
    - ./tests:/app/tests:ro
    - ./storage:/app/storage
    - ./models:/app/models
  environment:
    - DEBUG=true
    - ENVIRONMENT=development
    - DB_HOST=db
    - DB_PORT=5432
    - DB_USER=visualvault
    - DB_PASSWORD=visualvault
    - DB_NAME=visualvault
    - REDIS_HOST=redis
    - REDIS_PORT=6379
  depends_on:
    db:
      condition: service_healthy
    redis:
      condition: service_healthy
  healthcheck:
    test: ["CMD", "python", "-c", "import httpx; httpx.get('http://localhost:8000/api/v1/health').raise_for_status()"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 40s
```

Let's break this down:

#### Build Configuration

```yaml
build:
  context: .
  target: development
```

| Option | Meaning |
|--------|---------|
| `context: .` | Build from current directory (where Dockerfile is) |
| `target: development` | Use the `development` stage from multi-stage Dockerfile |

**Alternative:** Use a pre-built image instead:
```yaml
image: visualvault:latest
```

#### Port Mapping

```yaml
ports:
  - "8000:8000"
```

Format: `"HOST_PORT:CONTAINER_PORT"`

- Left side (8000): Port on your machine
- Right side (8000): Port inside the container

You access the app at `localhost:8000`, which routes to port 8000 in the container.

**Examples:**
```yaml
ports:
  - "3000:8000"   # Access at localhost:3000
  - "8000"        # Random host port, container port 8000
  - "127.0.0.1:8000:8000"  # Only accessible from localhost
```

#### Volume Mounts

```yaml
volumes:
  - ./app:/app/app:ro
  - ./tests:/app/tests:ro
  - ./storage:/app/storage
  - ./models:/app/models
```

Format: `"HOST_PATH:CONTAINER_PATH:OPTIONS"`

| Mount | Purpose |
|-------|---------|
| `./app:/app/app:ro` | Sync code for hot reload (read-only) |
| `./storage:/app/storage` | Persist uploaded files |
| `./models:/app/models` | Persist ML model weights |

**The `:ro` suffix** means read-only. The container can't modify these files - good for security and preventing accidental changes.

**Why mount code?** So changes on your machine immediately appear in the container. Combined with `--reload`, uvicorn detects changes and restarts.

#### Environment Variables

```yaml
environment:
  - DEBUG=true
  - DB_HOST=db
  - REDIS_HOST=redis
```

Sets environment variables inside the container. Notice:
- `DB_HOST=db` - Uses the service name as hostname
- Docker's internal DNS resolves `db` to the database container's IP

**Alternative:** Load from a file:
```yaml
env_file:
  - .env
```

#### Dependencies

```yaml
depends_on:
  db:
    condition: service_healthy
  redis:
    condition: service_healthy
```

**What it does:** Ensures `db` and `redis` are healthy before starting `api`.

**Conditions:**
- `service_started` - Just wait for container to start (default)
- `service_healthy` - Wait for healthcheck to pass
- `service_completed_successfully` - Wait for container to exit successfully

**Why `service_healthy`?** A database container starts quickly, but PostgreSQL inside might take seconds to be ready. `service_healthy` waits for the actual database to accept connections.

#### Health Checks

```yaml
healthcheck:
  test: ["CMD", "python", "-c", "import httpx; httpx.get('http://localhost:8000/api/v1/health').raise_for_status()"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

| Option | Meaning |
|--------|---------|
| `test` | Command to run to check health |
| `interval` | Time between checks |
| `timeout` | Max time for check to complete |
| `retries` | Failures before marking unhealthy |
| `start_period` | Grace period for container startup |

**The test command:** Runs Python to make an HTTP request to the health endpoint. If it fails, the container is unhealthy.

---

### The Database Service

```yaml
db:
  image: postgres:15-alpine
  ports:
    - "5432:5432"
  environment:
    - POSTGRES_USER=visualvault
    - POSTGRES_PASSWORD=visualvault
    - POSTGRES_DB=visualvault
  volumes:
    - postgres_data:/var/lib/postgresql/data
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U visualvault -d visualvault"]
    interval: 5s
    timeout: 5s
    retries: 5
```

#### Named Volumes

```yaml
volumes:
  - postgres_data:/var/lib/postgresql/data
```

Unlike bind mounts (`./app:/app/app`), this is a **named volume** managed by Docker.

- Data persists even if container is removed
- Defined at the bottom of the file
- Better performance than bind mounts

**Without this:** Database data would be lost every time you run `docker-compose down`.

#### PostgreSQL Health Check

```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U visualvault -d visualvault"]
```

`pg_isready` is a PostgreSQL utility that checks if the database is accepting connections.

---

### The Redis Service

```yaml
redis:
  image: redis:7-alpine
  ports:
    - "6379:6379"
  volumes:
    - redis_data:/data
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 5s
    timeout: 5s
    retries: 5
  command: redis-server --appendonly yes
```

#### Custom Command

```yaml
command: redis-server --appendonly yes
```

Overrides the default command from the image. `--appendonly yes` enables persistence so data survives restarts.

---

### The Worker Service

```yaml
worker:
  build:
    context: .
    target: development
  command: celery -A app.workers.celery_app worker --loglevel=info
  volumes:
    - ./app:/app/app:ro
    - ./storage:/app/storage
    - ./models:/app/models
  environment:
    # Same as api...
  depends_on:
    db:
      condition: service_healthy
    redis:
      condition: service_healthy
```

**Same image, different command.** The worker uses the same Dockerfile but runs Celery instead of uvicorn.

---

### Volume Definitions

```yaml
volumes:
  postgres_data:
  redis_data:
```

Declares named volumes. Docker manages where they're stored on disk.

**Inspect a volume:**
```bash
docker volume inspect visualvault_postgres_data
```

---

## Common Commands

### Starting Services

```bash
# Start all services in background
docker-compose up -d

# Start and rebuild images
docker-compose up -d --build

# Start specific service
docker-compose up -d api

# Start with logs visible
docker-compose up
```

### Stopping Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (DELETES DATA!)
docker-compose down -v

# Stop specific service
docker-compose stop api
```

### Viewing Status

```bash
# List running containers
docker-compose ps

# List all containers (including stopped)
docker-compose ps -a

# View logs
docker-compose logs

# Follow logs
docker-compose logs -f

# Logs for specific service
docker-compose logs -f api
```

### Executing Commands

```bash
# Run command in running container
docker-compose exec api bash

# Run command in new container
docker-compose run --rm api pytest

# Run database migrations
docker-compose exec api alembic upgrade head
```

### Rebuilding

```bash
# Rebuild specific service
docker-compose build api

# Rebuild without cache
docker-compose build --no-cache api

# Pull latest base images and rebuild
docker-compose build --pull api
```

---

## Networking

Docker Compose creates a network for your services automatically.

```
┌─────────────────────────────────────────────┐
│           visualvault_default               │
│                 (network)                   │
│                                             │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐     │
│  │   api   │  │   db    │  │  redis  │     │
│  │  :8000  │  │  :5432  │  │  :6379  │     │
│  └─────────┘  └─────────┘  └─────────┘     │
│       │            │            │          │
│       └────────────┴────────────┘          │
│            Internal DNS                     │
└─────────────────────────────────────────────┘
        │
        │ Port mapping
        ▼
   localhost:8000
```

- Services communicate using service names as hostnames
- `api` can reach database at `db:5432`
- Only explicitly mapped ports are accessible from your machine

---

## Profiles (Optional Services)

```yaml
flower:
  # ... config ...
  profiles:
    - monitoring
```

Services with profiles don't start by default:

```bash
# Normal start (no flower)
docker-compose up -d

# Start with monitoring profile
docker-compose --profile monitoring up -d
```

---

## Environment Files

Instead of inline environment variables:

```yaml
# docker-compose.yml
services:
  api:
    env_file:
      - .env
      - .env.local  # Overrides .env
```

```bash
# .env
DEBUG=false
DB_HOST=db

# .env.local (not committed to git)
DB_PASSWORD=my-secret-password
```

---

## Development vs Production

For production, create `docker-compose.prod.yml`:

```yaml
# docker-compose.prod.yml
services:
  api:
    build:
      target: production
    volumes: []  # No code mounts
    environment:
      - DEBUG=false
```

Run with:
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

The second file overrides the first.

---

## Common Issues

### Port already in use
```
Error: bind: address already in use
```
**Solution:** Stop the conflicting service or change the port:
```yaml
ports:
  - "8001:8000"  # Use different host port
```

### Container keeps restarting
```bash
# Check logs
docker-compose logs api

# Common causes:
# - Application crash
# - Missing environment variables
# - Database not ready
```

### Changes not reflected
```bash
# Rebuild the image
docker-compose up -d --build

# Or restart the service
docker-compose restart api
```

### Volume permission issues
```bash
# Check ownership inside container
docker-compose exec api ls -la /app/storage

# Fix permissions
sudo chown -R $USER:$USER ./storage
```

---

## Further Reading

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Compose File Reference](https://docs.docker.com/compose/compose-file/)
- [Networking in Compose](https://docs.docker.com/compose/networking/)
