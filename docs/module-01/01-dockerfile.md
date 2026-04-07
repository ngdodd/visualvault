# Understanding Dockerfiles

## What is Docker?

Docker is a platform that packages applications into **containers** - lightweight, standalone units that include everything needed to run the software: code, runtime, libraries, and system tools.

Think of a container like a shipping container for software. Just as shipping containers standardized global trade by providing a consistent way to transport goods, Docker containers standardize software deployment by providing a consistent way to run applications.

**Why use Docker for ML projects?**
- **Reproducibility**: Same environment everywhere (your laptop, colleague's machine, production server)
- **Dependency isolation**: No more "it works on my machine" problems
- **Easy deployment**: Package once, run anywhere
- **ML-specific**: Ensures consistent PyTorch/TensorFlow versions, CUDA drivers, etc.

---

## What is a Dockerfile?

A **Dockerfile** is a text file containing instructions to build a Docker image. Think of it as a recipe - each instruction adds a "layer" to the image.

```
Dockerfile → (docker build) → Image → (docker run) → Container
```

- **Image**: A snapshot/template (like a class in programming)
- **Container**: A running instance of an image (like an object)

---

## Our Dockerfile Explained

Let's walk through `visualvault/Dockerfile` line by line:

### Stage 1: Base Image

```dockerfile
FROM python:3.11-slim as base
```

**What it does:** Starts from an official Python image.

- `python:3.11-slim` - Python 3.11 on Debian Linux, "slim" variant (smaller size)
- `as base` - Names this stage "base" so we can reference it later

**Why slim?** The full Python image is ~1GB, slim is ~150MB. For ML apps, we add only what we need.

**Alternatives:**
- `python:3.11` - Full image with more tools (larger)
- `python:3.11-alpine` - Even smaller but can have compatibility issues

---

### Environment Variables

```dockerfile
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
```

**What it does:** Sets environment variables that persist in the image.

| Variable | Purpose |
|----------|---------|
| `PYTHONDONTWRITEBYTECODE=1` | Don't create `.pyc` files (saves space) |
| `PYTHONUNBUFFERED=1` | Print output immediately (important for logs) |
| `PYTHONFAULTHANDLER=1` | Better error tracebacks |
| `PIP_NO_CACHE_DIR=1` | Don't cache pip downloads (saves space) |
| `PIP_DISABLE_PIP_VERSION_CHECK=1` | Faster pip operations |

---

### System Dependencies

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    libjpeg-dev \
    libpng-dev \
    libgl1 \
    libglib2.0-0 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*
```

**What it does:** Installs Linux packages needed by our Python libraries.

| Package | Why We Need It |
|---------|----------------|
| `libpq-dev` | PostgreSQL client library (for psycopg2) |
| `libjpeg-dev`, `libpng-dev` | Image processing (for Pillow) |
| `libgl1`, `libglib2.0-0` | Graphics libraries (for OpenCV) |
| `build-essential` | C compiler (for building Python packages) |

**Best Practices:**
- `--no-install-recommends` - Only install required packages, not suggestions
- `rm -rf /var/lib/apt/lists/*` - Delete package lists to reduce image size
- Combine commands with `&&` - Creates one layer instead of multiple

---

### Working Directory

```dockerfile
WORKDIR /app
```

**What it does:** Sets the working directory for subsequent commands. Like `cd /app` but also creates the directory if it doesn't exist.

All following commands (`COPY`, `RUN`, etc.) will execute relative to `/app`.

---

### Stage 2: Development Image

```dockerfile
FROM base as development
```

**What it does:** Starts a new stage from our `base` image.

**Multi-stage builds** let us create different images for different purposes:
- `development` - Has dev tools, supports hot reload
- `production` - Minimal, optimized for deployment

---

### Copying Files

```dockerfile
COPY pyproject.toml README.md ./
COPY app/ ./app/
```

**What it does:** Copies files from your computer into the image.

```
COPY <source on your machine> <destination in container>
```

**Why copy in this order?**
1. Copy dependency files first (`pyproject.toml`)
2. Install dependencies
3. Copy application code last

This optimizes Docker's **layer caching**. If you only change `app/` code, Docker reuses the cached dependency layer instead of reinstalling everything.

---

### Installing Dependencies

```dockerfile
RUN pip install --upgrade pip && \
    pip install -e ".[dev]"
```

**What it does:**
- Updates pip to latest version
- Installs the package in "editable" mode with dev dependencies

**What is `-e` (editable mode)?**
- Changes to code are reflected immediately without reinstalling
- Essential for development with hot reload

**What is `.[dev]`?**
- `.` means "install the current directory as a package"
- `[dev]` means "also install optional dev dependencies" (pytest, ruff, etc.)

---

### Copying Remaining Files

```dockerfile
COPY . .
```

**What it does:** Copies everything else (tests, configs, etc.)

**Note:** This comes AFTER installing dependencies to maximize cache efficiency.

---

### Creating a Non-Root User

```dockerfile
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser
```

**What it does:** Creates a regular user and switches to it.

**Why?** Security best practice. Running as root inside a container is risky - if an attacker exploits your app, they have root access. A non-root user limits the damage.

---

### Exposing Ports

```dockerfile
EXPOSE 8000
```

**What it does:** Documents that the container listens on port 8000.

**Important:** This is just documentation! You still need `-p 8000:8000` when running the container to actually publish the port.

---

### Default Command

```dockerfile
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

**What it does:** Specifies the default command to run when the container starts.

| Part | Meaning |
|------|---------|
| `uvicorn` | ASGI server for FastAPI |
| `app.main:app` | Python path to the FastAPI application |
| `--host 0.0.0.0` | Listen on all network interfaces |
| `--port 8000` | Listen on port 8000 |
| `--reload` | Auto-reload on code changes (dev only!) |

**CMD vs ENTRYPOINT:**
- `CMD` - Default command, can be overridden
- `ENTRYPOINT` - Always runs, CMD becomes arguments to it

---

### Stage 3: Production Image

```dockerfile
FROM base as production

COPY pyproject.toml README.md ./
COPY app/ ./app/

RUN pip install --upgrade pip && \
    pip install .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

**Differences from development:**
- `pip install .` instead of `pip install -e ".[dev]"` - No dev dependencies, not editable
- `--workers 4` instead of `--reload` - Multiple workers for performance, no hot reload

---

## Building and Running

### Build the image

```bash
# Build development image
docker build --target development -t visualvault:dev .

# Build production image
docker build --target production -t visualvault:prod .
```

### Run a container

```bash
docker run -p 8000:8000 visualvault:dev
```

### Useful commands

```bash
# List images
docker images

# List running containers
docker ps

# View container logs
docker logs <container_id>

# Enter a running container
docker exec -it <container_id> bash

# Stop a container
docker stop <container_id>

# Remove an image
docker rmi visualvault:dev
```

---

## Layer Caching Visualized

```
Layer 1: FROM python:3.11-slim     ─┐
Layer 2: ENV ...                    │ Cached if unchanged
Layer 3: RUN apt-get install...     │
Layer 4: WORKDIR /app              ─┘
Layer 5: COPY pyproject.toml       ─┐ Rebuilds if pyproject.toml changes
Layer 6: RUN pip install           ─┘
Layer 7: COPY app/                 ─── Rebuilds on any code change
Layer 8: CMD ...                   ─── Rebuilds if command changes
```

**Optimization tip:** Put things that change frequently (your code) at the bottom. Things that rarely change (system dependencies) at the top.

---

## Common Issues

### Image too large
- Use slim/alpine base images
- Clean up in the same RUN command
- Use multi-stage builds
- Add `.dockerignore` file

### Build is slow
- Order COPY commands for better caching
- Combine RUN commands
- Use BuildKit: `DOCKER_BUILDKIT=1 docker build .`

### Permission errors
- Make sure files are owned by the non-root user
- Check volume mount permissions

---

## Further Reading

- [Dockerfile Reference](https://docs.docker.com/engine/reference/builder/)
- [Best Practices for Dockerfiles](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)
- [Multi-stage Builds](https://docs.docker.com/build/building/multi-stage/)
