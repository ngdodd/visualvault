# File Validation: Security and Integrity

## Why Validate?

Accepting file uploads is risky:

1. **Malware** - Executable files disguised as images
2. **Resource exhaustion** - Extremely large files
3. **Path traversal** - Malicious filenames (e.g., `../../../etc/passwd`)
4. **Incorrect types** - PDF claiming to be JPEG
5. **Corrupted files** - Incomplete or broken uploads

**Never trust client-provided data!**

---

## Validation Layers

```
┌─────────────────────────────────────────────────────────────┐
│                    Upload Request                           │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: Content-Type Check (fast, weak)                    │
│ Check if claimed MIME type is allowed                       │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: File Size Check (fast)                             │
│ Reject oversized files early                                │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: Magic Bytes / Header Check (fast, moderate)        │
│ Verify actual file format matches claim                     │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Layer 4: Full Parse Validation (slower, strong)             │
│ Actually parse the file to verify integrity                 │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Layer 5: Malware Scan (optional, slow)                      │
│ Scan with antivirus in production                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Layer 1: Content-Type Validation

The browser sends the MIME type, but it can be spoofed:

```python
ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/bmp",
    "image/tiff",
}

def validate_content_type(content_type: str) -> bool:
    """Check if content type is allowed (weak check)."""
    return content_type in ALLOWED_IMAGE_TYPES
```

**This is a first pass only!** Anyone can send:
```bash
curl -X POST /upload \
  -H "Content-Type: image/jpeg" \
  -d @malware.exe
```

---

## Layer 2: File Size Validation

Check size to prevent resource exhaustion:

```python
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

async def validate_file_size(file: UploadFile) -> tuple[int, bytes]:
    """
    Read file and validate size.
    Returns (size, content) or raises HTTPException.
    """
    content = await file.read()
    size = len(content)

    if size == 0:
        raise HTTPException(400, "Empty file")

    if size > MAX_FILE_SIZE:
        raise HTTPException(
            413,
            f"File size ({size / 1024 / 1024:.1f}MB) "
            f"exceeds maximum ({MAX_FILE_SIZE / 1024 / 1024:.0f}MB)"
        )

    return size, content
```

### Streaming Size Check

For very large files, check while reading:

```python
async def read_with_limit(file: UploadFile, max_size: int) -> bytes:
    """Read file with size limit."""
    chunks = []
    total_size = 0

    while chunk := await file.read(8192):
        total_size += len(chunk)
        if total_size > max_size:
            raise HTTPException(413, "File too large")
        chunks.append(chunk)

    return b''.join(chunks)
```

---

## Layer 3: Magic Bytes Validation

Files have signature bytes at the beginning:

| Format | Magic Bytes (hex) | ASCII |
|--------|-------------------|-------|
| JPEG | `FF D8 FF` | ... |
| PNG | `89 50 4E 47 0D 0A 1A 0A` | .PNG.... |
| GIF | `47 49 46 38` | GIF8 |
| WebP | `52 49 46 46 ... 57 45 42 50` | RIFF...WEBP |
| PDF | `25 50 44 46` | %PDF |

```python
IMAGE_SIGNATURES = {
    b'\xff\xd8\xff': 'image/jpeg',
    b'\x89PNG\r\n\x1a\n': 'image/png',
    b'GIF87a': 'image/gif',
    b'GIF89a': 'image/gif',
    b'RIFF': 'image/webp',  # Needs additional check
    b'BM': 'image/bmp',
}

def detect_image_type(content: bytes) -> str | None:
    """Detect image type from magic bytes."""
    for signature, mime_type in IMAGE_SIGNATURES.items():
        if content.startswith(signature):
            # Special check for WebP (RIFF....WEBP)
            if signature == b'RIFF':
                if len(content) >= 12 and content[8:12] == b'WEBP':
                    return mime_type
                continue
            return mime_type
    return None


def validate_magic_bytes(content: bytes, claimed_type: str) -> bool:
    """Verify file content matches claimed type."""
    detected = detect_image_type(content)
    return detected == claimed_type
```

---

## Layer 4: Full Image Validation

Use Pillow to actually parse and verify the image:

```python
from PIL import Image
import io

def validate_image_integrity(file_content: bytes) -> tuple[bool, str]:
    """
    Fully validate an image by parsing it.

    Returns:
        (is_valid, error_message)
    """
    try:
        file_obj = io.BytesIO(file_content)
        img = Image.open(file_obj)

        # verify() checks for corruption without fully decoding
        img.verify()

        return True, ""

    except Image.UnidentifiedImageError:
        return False, "File is not a recognized image format"

    except Image.DecompressionBombError:
        return False, "Image is too large (possible decompression bomb)"

    except Exception as e:
        return False, f"Invalid or corrupted image: {str(e)}"
```

### Decompression Bombs

A small file can decompress to huge dimensions:

```python
# A 42KB file that decompresses to 16384 x 16384 = 1GB in memory!
```

Pillow protects against this:

```python
from PIL import Image

# Default limit: 178,956,970 pixels
# Override if needed (carefully!)
Image.MAX_IMAGE_PIXELS = 100_000_000  # 100 megapixels
```

---

## Layer 5: Malware Scanning (Production)

For production systems, consider antivirus scanning:

```python
import clamd  # ClamAV Python client

def scan_for_malware(file_content: bytes) -> tuple[bool, str]:
    """Scan file with ClamAV."""
    try:
        cd = clamd.ClamdUnixSocket()
        result = cd.instream(io.BytesIO(file_content))

        # result: {'stream': ('OK', None)} or {'stream': ('FOUND', 'Virus.Name')}
        status, virus_name = result['stream']

        if status == 'OK':
            return True, ""
        else:
            return False, f"Malware detected: {virus_name}"

    except Exception as e:
        # Log error, but don't fail (scan is optional)
        logger.warning(f"Malware scan failed: {e}")
        return True, ""
```

---

## Filename Sanitization

Never trust user-provided filenames:

```python
import os
import re
import uuid

def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to prevent path traversal and other attacks.
    """
    # Remove path components
    filename = os.path.basename(filename)

    # Remove dangerous characters
    filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', filename)

    # Limit length
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:200-len(ext)] + ext

    # If nothing left, use a default
    if not filename or filename == '.':
        filename = 'unnamed'

    return filename


def generate_unique_filename(original: str) -> str:
    """Generate a unique filename while preserving extension."""
    ext = os.path.splitext(original)[1].lower()
    unique_id = uuid.uuid4().hex[:16]
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{unique_id}{ext}"
```

### Path Traversal Attacks

```python
# Dangerous filenames:
"../../../etc/passwd"
"....//....//....//etc/passwd"
"/absolute/path/file"
"file\x00.txt"  # Null byte injection

# Always use basename and generate new names:
safe_name = generate_unique_filename(user_filename)
```

---

## Our Complete Validation Flow

```python
# app/services/storage.py

class StorageService:
    ALLOWED_IMAGE_TYPES = {
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "image/bmp",
        "image/tiff",
    }
    MAX_FILE_SIZE = 50 * 1024 * 1024

    def validate_image(
        self,
        content_type: str,
        file_size: int,
    ) -> tuple[bool, str]:
        """Validate file type and size."""
        # Type check
        if content_type not in self.ALLOWED_IMAGE_TYPES:
            allowed = ", ".join(
                t.split("/")[1].upper()
                for t in self.ALLOWED_IMAGE_TYPES
            )
            return False, f"File type not allowed. Allowed: {allowed}"

        # Size check
        if file_size > self.MAX_FILE_SIZE:
            max_mb = self.MAX_FILE_SIZE / (1024 * 1024)
            return False, f"File exceeds maximum size ({max_mb:.0f}MB)"

        return True, ""
```

```python
# app/api/v1/assets.py

@router.post("/upload")
async def upload_image(user: CurrentUserDep, db: DbSessionDep, file: UploadFile):
    storage = get_storage_service()

    # 1. Content-Type check (weak but fast)
    if not file.content_type:
        raise HTTPException(400, "Could not determine file type")

    is_valid, error = storage.validate_image(file.content_type, 0)
    if not is_valid and "type" in error.lower():
        raise HTTPException(400, error)

    # 2. Read content and check size
    content = await file.read()
    file_size = len(content)

    if file_size == 0:
        raise HTTPException(400, "Empty file")

    is_valid, error = storage.validate_image(file.content_type, file_size)
    if not is_valid:
        raise HTTPException(413 if "size" in error.lower() else 400, error)

    # 3. Full image validation
    file_obj = io.BytesIO(content)
    is_valid, error = validate_image_integrity(file_obj)
    if not is_valid:
        raise HTTPException(400, error)

    # 4. Proceed with storage...
```

---

## Extension Validation

Double-check the extension matches the content:

```python
MIME_TO_EXTENSIONS = {
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
    "image/gif": {".gif"},
    "image/webp": {".webp"},
    "image/bmp": {".bmp"},
}

def validate_extension(filename: str, content_type: str) -> bool:
    """Verify file extension matches content type."""
    ext = os.path.splitext(filename)[1].lower()
    allowed_exts = MIME_TO_EXTENSIONS.get(content_type, set())
    return ext in allowed_exts
```

---

## Security Recommendations

### 1. Validate Everything
```python
# Content-Type (weak)
# Size (important)
# Magic bytes (moderate)
# Full parse (strong)
```

### 2. Never Trust Client Data
```python
# Don't trust: content_type, filename, size header
# Verify: actual content
```

### 3. Generate New Filenames
```python
# Never use user-provided filenames directly
safe_name = generate_unique_filename(original)
```

### 4. Store Outside Web Root
```python
# Don't: /var/www/html/uploads/
# Do: /var/uploads/ (served through authenticated endpoint)
```

### 5. Use Dedicated Upload Endpoint
```python
# Don't: Accept files in any endpoint
# Do: Single, well-validated upload endpoint
```

### 6. Log Upload Attempts
```python
logger.info(
    "File upload",
    user_id=user.id,
    filename=file.filename,
    size=file_size,
    content_type=file.content_type,
    accepted=True,
)
```

---

## Further Reading

- [OWASP File Upload Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html)
- [Pillow Security Considerations](https://pillow.readthedocs.io/en/stable/reference/Image.html#security)
- [ClamAV](https://www.clamav.net/) - Open source antivirus
