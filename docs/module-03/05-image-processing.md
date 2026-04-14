# Image Processing: Working with Pillow

## What is Pillow?

Pillow is the friendly fork of PIL (Python Imaging Library). It provides:

- Image opening and format detection
- Resizing and transformations
- Color analysis
- Format conversion
- Metadata extraction

```bash
pip install pillow
```

---

## Basic Operations

### Opening Images

```python
from PIL import Image

# From file path
img = Image.open("photo.jpg")

# From file-like object
img = Image.open(file_object)

# From bytes
import io
img = Image.open(io.BytesIO(image_bytes))
```

### Image Properties

```python
img = Image.open("photo.jpg")

img.size      # (width, height) tuple
img.width     # Width in pixels
img.height    # Height in pixels
img.format    # 'JPEG', 'PNG', etc.
img.mode      # 'RGB', 'RGBA', 'L' (grayscale), etc.
img.info      # Dictionary of metadata
```

---

## Our Image Utilities

### Get Image Dimensions

```python
# app/utils/image.py

from typing import BinaryIO
from PIL import Image

def get_image_dimensions(file: BinaryIO) -> tuple[int, int] | None:
    """
    Get dimensions of an image file.

    Args:
        file: File-like object containing image data

    Returns:
        Tuple of (width, height) or None if not valid

    Note:
        File position is reset after reading.
    """
    try:
        pos = file.tell()  # Save position
        img = Image.open(file)
        dimensions = img.size
        file.seek(pos)  # Reset position
        return dimensions
    except Exception:
        file.seek(0)
        return None
```

**Usage:**
```python
import io

content = await upload_file.read()
file_obj = io.BytesIO(content)

dimensions = get_image_dimensions(file_obj)
if dimensions:
    width, height = dimensions
    print(f"Image is {width}x{height}")
```

---

### Validate Image Integrity

```python
def validate_image_integrity(file: BinaryIO) -> tuple[bool, str]:
    """
    Validate that a file is a valid, uncorrupted image.

    The verify() method checks image integrity without
    fully decoding the image data.

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        pos = file.tell()
        img = Image.open(file)
        img.verify()  # Check for corruption
        file.seek(pos)
        return True, ""
    except Image.UnidentifiedImageError:
        file.seek(0)
        return False, "File is not a recognized image format"
    except Image.DecompressionBombError:
        file.seek(0)
        return False, "Image is too large (possible decompression bomb)"
    except Exception as e:
        file.seek(0)
        return False, f"Invalid or corrupted image: {str(e)}"
```

**Key Points:**
- `verify()` checks structure without full decode
- Detects corrupted files
- Catches decompression bombs
- Always reset file position

---

### Detect Image Format

```python
def get_image_format(file: BinaryIO) -> str | None:
    """
    Detect the actual format of an image.

    Don't trust Content-Type headers - verify the file!
    """
    try:
        pos = file.tell()
        img = Image.open(file)
        fmt = img.format  # 'JPEG', 'PNG', 'GIF', etc.
        file.seek(pos)
        return fmt
    except Exception:
        file.seek(0)
        return None
```

**Usage:**
```python
# Verify format matches claimed type
MIME_TO_FORMAT = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/gif": "GIF",
    "image/webp": "WEBP",
}

actual_format = get_image_format(file_obj)
expected_format = MIME_TO_FORMAT.get(claimed_content_type)

if actual_format != expected_format:
    raise ValueError("File format doesn't match Content-Type")
```

---

### Create Thumbnails

```python
def create_thumbnail(
    file: BinaryIO,
    max_size: tuple[int, int] = (256, 256),
) -> bytes:
    """
    Create a thumbnail from an image.

    Args:
        file: Source image
        max_size: Maximum (width, height)

    Returns:
        Thumbnail as JPEG bytes
    """
    pos = file.tell()
    img = Image.open(file)

    # Convert RGBA/P to RGB for JPEG output
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # Create thumbnail (modifies in place, maintains aspect ratio)
    img.thumbnail(max_size, Image.Resampling.LANCZOS)

    # Save to bytes
    output = io.BytesIO()
    img.save(output, format="JPEG", quality=85, optimize=True)

    file.seek(pos)
    return output.getvalue()
```

**Thumbnail vs Resize:**
- `thumbnail()` - Shrinks to fit within max_size, never enlarges
- `resize()` - Forces exact dimensions

---

### Resize Image

```python
def resize_image(
    file: BinaryIO,
    width: int | None = None,
    height: int | None = None,
    maintain_aspect: bool = True,
) -> bytes:
    """
    Resize an image to specified dimensions.

    Provide width OR height to auto-calculate the other.
    Provide both to fit within bounds (if maintain_aspect=True).
    """
    pos = file.tell()
    img = Image.open(file)
    original_format = img.format or "JPEG"
    orig_w, orig_h = img.size

    if maintain_aspect:
        if width and not height:
            ratio = width / orig_w
            height = int(orig_h * ratio)
        elif height and not width:
            ratio = height / orig_h
            width = int(orig_w * ratio)
        elif width and height:
            # Fit within bounds
            w_ratio = width / orig_w
            h_ratio = height / orig_h
            ratio = min(w_ratio, h_ratio)
            width = int(orig_w * ratio)
            height = int(orig_h * ratio)

    if width and height:
        img = img.resize((width, height), Image.Resampling.LANCZOS)

    # Handle format-specific requirements
    if original_format == "JPEG" and img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    output = io.BytesIO()
    save_kwargs = {"format": original_format}

    if original_format == "JPEG":
        save_kwargs["quality"] = 90
        save_kwargs["optimize"] = True
    elif original_format == "PNG":
        save_kwargs["optimize"] = True

    img.save(output, **save_kwargs)
    file.seek(pos)

    return output.getvalue()
```

---

### Extract Dominant Colors

```python
from collections import Counter

def extract_dominant_colors(
    file: BinaryIO,
    num_colors: int = 5,
) -> list[dict]:
    """
    Extract dominant colors from an image.

    Returns list of colors with hex code and percentage.
    """
    pos = file.tell()
    img = Image.open(file)

    # Resize for faster processing
    img.thumbnail((150, 150))

    # Convert to RGB
    if img.mode != "RGB":
        img = img.convert("RGB")

    # Quantize to reduce colors
    quantized = img.quantize(colors=num_colors)
    palette = quantized.getpalette()

    # Count pixels per color
    pixels = list(quantized.getdata())
    color_counts = Counter(pixels)
    total = len(pixels)

    # Build result
    colors = []
    for idx, count in color_counts.most_common(num_colors):
        if palette:
            r = palette[idx * 3]
            g = palette[idx * 3 + 1]
            b = palette[idx * 3 + 2]
            colors.append({
                "hex": f"#{r:02x}{g:02x}{b:02x}",
                "rgb": [r, g, b],
                "percentage": round((count / total) * 100, 2),
            })

    file.seek(pos)
    return colors
```

**Output:**
```python
[
    {"hex": "#3498db", "rgb": [52, 152, 219], "percentage": 35.2},
    {"hex": "#2ecc71", "rgb": [46, 204, 113], "percentage": 28.4},
    {"hex": "#e74c3c", "rgb": [231, 76, 60], "percentage": 15.1},
]
```

---

## Image Modes

| Mode | Description | Bytes/Pixel |
|------|-------------|-------------|
| `1` | Black and white | 1 bit |
| `L` | Grayscale | 1 |
| `P` | Palette (indexed) | 1 |
| `RGB` | Color | 3 |
| `RGBA` | Color + alpha | 4 |
| `CMYK` | Print colors | 4 |

### Converting Modes

```python
# RGB to Grayscale
gray = img.convert("L")

# RGBA to RGB (for JPEG)
rgb = img.convert("RGB")

# Add alpha channel
rgba = img.convert("RGBA")
```

---

## Resampling Filters

When resizing, choose the appropriate filter:

| Filter | Quality | Speed | Use Case |
|--------|---------|-------|----------|
| `NEAREST` | Lowest | Fastest | Pixel art |
| `BOX` | Low | Fast | Downscaling |
| `BILINEAR` | Medium | Medium | General |
| `HAMMING` | Medium | Medium | General |
| `BICUBIC` | High | Slow | Photos |
| `LANCZOS` | Highest | Slowest | Best quality |

```python
# High quality resize
img.resize((800, 600), Image.Resampling.LANCZOS)

# Fast thumbnail
img.thumbnail((256, 256), Image.Resampling.BILINEAR)
```

---

## EXIF Orientation

Photos from phones often have EXIF orientation data:

```python
from PIL import ImageOps

def fix_orientation(img: Image.Image) -> Image.Image:
    """Apply EXIF orientation to image pixels."""
    return ImageOps.exif_transpose(img)


# Usage
img = Image.open(file)
img = fix_orientation(img)
```

Without this, rotated photos may appear sideways.

---

## Memory Management

### Decompression Bombs

A small file can expand to huge dimensions:

```python
from PIL import Image

# Default limit: 178,956,970 pixels
# A 13,400 x 13,400 image

# Pillow will raise DecompressionBombError if exceeded
try:
    img = Image.open(suspicious_file)
except Image.DecompressionBombError:
    print("Image too large!")
```

### Handling Large Images

```python
# Process in chunks (not always possible)
# Or set a higher limit carefully:
Image.MAX_IMAGE_PIXELS = 200_000_000  # 200 megapixels

# Or disable the check (dangerous!)
Image.MAX_IMAGE_PIXELS = None
```

---

## Format-Specific Notes

### JPEG

```python
# Save with quality
img.save("output.jpg", quality=85, optimize=True)

# JPEG doesn't support transparency
if img.mode == "RGBA":
    img = img.convert("RGB")
```

### PNG

```python
# PNG supports transparency
img.save("output.png", optimize=True)

# Compress more (slower)
img.save("output.png", compress_level=9)
```

### WebP

```python
# WebP supports both lossy and lossless
img.save("output.webp", quality=85)  # Lossy
img.save("output.webp", lossless=True)  # Lossless
```

### GIF

```python
# GIF is palette-based (256 colors max)
# Animated GIFs need special handling
if img.is_animated:
    # Handle frames
    for frame in ImageSequence.Iterator(img):
        process(frame)
```

---

## Integration Example

```python
# In upload endpoint

async def upload_image(file: UploadFile, user: CurrentUserDep, db: DbSessionDep):
    content = await file.read()
    file_obj = io.BytesIO(content)

    # 1. Validate integrity
    is_valid, error = validate_image_integrity(file_obj)
    if not is_valid:
        raise HTTPException(400, error)

    # 2. Get dimensions
    dimensions = get_image_dimensions(file_obj)

    # 3. Create thumbnail for preview
    thumbnail_bytes = create_thumbnail(file_obj, max_size=(256, 256))

    # 4. Extract colors for search
    colors = extract_dominant_colors(file_obj)

    # 5. Save original
    file_obj.seek(0)
    storage_path = await storage.save_file(file_obj, ...)

    # 6. Save thumbnail
    thumb_path = await storage.save_file(
        io.BytesIO(thumbnail_bytes),
        filename=f"thumb_{file.filename}",
        ...
    )

    # Create asset record
    asset = Asset(
        width=dimensions[0] if dimensions else None,
        height=dimensions[1] if dimensions else None,
        ml_colors=json.dumps(colors),
        ...
    )
```

---

## Performance Tips

### 1. Process Thumbnails, Not Originals

```python
# For analysis, use smaller version
img.thumbnail((512, 512))
colors = analyze_colors(img)  # Much faster!
```

### 2. Use Lazy Loading

```python
# Image.open() is lazy - doesn't load pixels yet
img = Image.open(file)  # Fast, just reads header

# Pixels loaded on first access
pixels = img.load()  # Actually loads image
```

### 3. Close Images

```python
# Free memory when done
img = Image.open(file)
# ... process ...
img.close()

# Or use context manager
with Image.open(file) as img:
    # ... process ...
# Automatically closed
```

### 4. Avoid Multiple Opens

```python
# Bad: Opens file multiple times
dims = get_image_dimensions(file)
colors = extract_colors(file)  # Opens again

# Better: Open once, do multiple operations
img = Image.open(file)
dims = img.size
colors = analyze(img)
```

---

## Further Reading

- [Pillow Documentation](https://pillow.readthedocs.io/)
- [Pillow Tutorial](https://pillow.readthedocs.io/en/stable/handbook/tutorial.html)
- [Image File Formats](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html)
