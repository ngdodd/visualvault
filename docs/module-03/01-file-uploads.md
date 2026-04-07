# File Uploads: Handling User Files

## How File Uploads Work

When a user uploads a file, the browser sends it using **multipart/form-data** encoding:

```
POST /upload HTTP/1.1
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary

------WebKitFormBoundary
Content-Disposition: form-data; name="file"; filename="photo.jpg"
Content-Type: image/jpeg

[binary data here]
------WebKitFormBoundary--
```

The server receives this and extracts:
- **filename**: Original name from the user's system
- **content_type**: MIME type (e.g., `image/jpeg`)
- **file data**: The actual file content

---

## FastAPI File Uploads

FastAPI provides two ways to handle uploads:

### 1. `bytes` - Small Files

```python
from fastapi import File

@router.post("/upload")
async def upload(file: bytes = File(...)):
    # 'file' is the entire file content in memory
    print(f"Received {len(file)} bytes")
```

**When to use:** Files under 1MB, when you need the whole file at once.

### 2. `UploadFile` - All Files (Recommended)

```python
from fastapi import File, UploadFile

@router.post("/upload")
async def upload(file: UploadFile = File(...)):
    # UploadFile is a file-like object
    print(f"Filename: {file.filename}")
    print(f"Content-Type: {file.content_type}")

    # Read the content
    content = await file.read()

    # Or read in chunks
    while chunk := await file.read(8192):
        process(chunk)
```

**Advantages of UploadFile:**
- Streams large files (doesn't load all into memory)
- Provides metadata (filename, content_type)
- Has async methods
- Auto-cleanup with temp files

---

## UploadFile Attributes and Methods

```python
@router.post("/upload")
async def upload(file: UploadFile):
    # Attributes
    file.filename      # "photo.jpg" (from client)
    file.content_type  # "image/jpeg" (from client)
    file.size          # File size in bytes (may be None)
    file.file          # Underlying file object

    # Async methods
    content = await file.read()        # Read all
    content = await file.read(1024)    # Read n bytes
    await file.seek(0)                 # Go to position
    await file.write(b"data")          # Write data
    await file.close()                 # Close file

    # SpooledTemporaryFile methods
    # For small files, stays in memory
    # For large files (>1MB), spools to disk
```

---

## Our Upload Endpoint

```python
# app/api/v1/assets.py

@router.post("/upload", response_model=AssetUploadResponse)
async def upload_image(
    user: CurrentUserDep,
    db: DbSessionDep,
    file: UploadFile = File(..., description="Image file to upload"),
) -> AssetUploadResponse:
    """Upload an image file."""
    settings = get_settings()
    storage = get_storage_service()

    # 1. Validate content type
    if not file.content_type:
        raise HTTPException(400, "Could not determine file type")

    is_valid, error = storage.validate_image(file.content_type, 0)
    if not is_valid:
        raise HTTPException(400, error)

    # 2. Read and check size
    content = await file.read()
    file_size = len(content)

    if file_size > settings.storage.max_file_size_bytes:
        raise HTTPException(413, "File too large")

    # 3. Create file-like object for processing
    import io
    file_obj = io.BytesIO(content)

    # 4. Validate image integrity
    is_valid, error = validate_image_integrity(file_obj)
    if not is_valid:
        raise HTTPException(400, error)

    # 5. Get dimensions
    dimensions = get_image_dimensions(file_obj)
    file_obj.seek(0)

    # 6. Save to storage
    storage_path = await storage.save_file(
        file_obj, file.filename, file.content_type, user.id
    )

    # 7. Create database record
    asset = Asset(
        user_id=user.id,
        original_filename=file.filename,
        storage_path=storage_path,
        # ... other fields
    )
    db.add(asset)

    return AssetUploadResponse(id=asset.id, ...)
```

---

## Handling Large Files

For very large files, read in chunks:

```python
@router.post("/upload-large")
async def upload_large(file: UploadFile):
    # Stream to storage without loading all into memory
    storage_path = get_temp_path()

    with open(storage_path, "wb") as dest:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            dest.write(chunk)
```

---

## Multiple File Uploads

### Single Field, Multiple Files

```python
from fastapi import File, UploadFile
from typing import List

@router.post("/upload-multiple")
async def upload_multiple(
    files: List[UploadFile] = File(...)
):
    results = []
    for file in files:
        # Process each file
        results.append({"filename": file.filename})
    return results
```

### HTML Form

```html
<form action="/upload-multiple" method="post" enctype="multipart/form-data">
    <input type="file" name="files" multiple>
    <button>Upload</button>
</form>
```

### cURL

```bash
curl -X POST http://localhost:8000/upload-multiple \
  -F "files=@image1.jpg" \
  -F "files=@image2.jpg"
```

---

## File Upload with Additional Data

Combine file upload with form fields:

```python
from fastapi import File, Form, UploadFile

@router.post("/upload-with-data")
async def upload_with_data(
    file: UploadFile = File(...),
    title: str = Form(...),
    description: str = Form(None),
    tags: List[str] = Form([]),
):
    return {
        "filename": file.filename,
        "title": title,
        "description": description,
        "tags": tags,
    }
```

**Request:**
```bash
curl -X POST http://localhost:8000/upload-with-data \
  -F "file=@photo.jpg" \
  -F "title=My Photo" \
  -F "description=A nice photo" \
  -F "tags=nature" \
  -F "tags=landscape"
```

---

## Error Handling

```python
@router.post("/upload")
async def upload(file: UploadFile = File(...)):
    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error reading file: {str(e)}"
        )
    finally:
        await file.close()  # Always close!
```

### Common HTTP Status Codes

| Code | Meaning | When to Use |
|------|---------|-------------|
| 201 | Created | Upload successful |
| 400 | Bad Request | Invalid file type, missing file |
| 413 | Payload Too Large | File exceeds size limit |
| 415 | Unsupported Media Type | Wrong content type |
| 500 | Internal Server Error | Storage failure |

---

## Client-Side Upload

### JavaScript (Fetch API)

```javascript
async function uploadFile(file, token) {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch('/api/v1/assets/upload', {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${token}`
        },
        body: formData
        // Note: Don't set Content-Type header!
        // Browser sets it with correct boundary
    });

    return response.json();
}
```

### Python (httpx)

```python
import httpx

async def upload_file(filepath: str, token: str):
    async with httpx.AsyncClient() as client:
        with open(filepath, 'rb') as f:
            files = {'file': (filepath, f, 'image/jpeg')}
            response = await client.post(
                'http://localhost:8000/api/v1/assets/upload',
                headers={'Authorization': f'Bearer {token}'},
                files=files
            )
    return response.json()
```

### cURL

```bash
curl -X POST http://localhost:8000/api/v1/assets/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/image.jpg"
```

---

## Upload Progress

For large files, track upload progress client-side:

```javascript
function uploadWithProgress(file, token, onProgress) {
    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        const formData = new FormData();
        formData.append('file', file);

        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) {
                const percent = (e.loaded / e.total) * 100;
                onProgress(percent);
            }
        });

        xhr.addEventListener('load', () => {
            if (xhr.status === 201) {
                resolve(JSON.parse(xhr.response));
            } else {
                reject(new Error(xhr.response));
            }
        });

        xhr.open('POST', '/api/v1/assets/upload');
        xhr.setRequestHeader('Authorization', `Bearer ${token}`);
        xhr.send(formData);
    });
}
```

---

## Best Practices

### 1. Always Validate
Don't trust client-provided data:
```python
# Don't trust content_type from client
# Validate actual file content
```

### 2. Set Size Limits
Prevent denial-of-service:
```python
if file_size > MAX_SIZE:
    raise HTTPException(413, "File too large")
```

### 3. Generate Unique Filenames
Prevent overwrites and path traversal:
```python
import uuid
safe_filename = f"{uuid.uuid4().hex}{extension}"
```

### 4. Clean Up Temp Files
Close and delete temporary files:
```python
try:
    # Process file
finally:
    await file.close()
```

### 5. Stream Large Files
Don't load entire file into memory:
```python
while chunk := await file.read(8192):
    process_chunk(chunk)
```

---

## Further Reading

- [FastAPI Request Files](https://fastapi.tiangolo.com/tutorial/request-files/)
- [Starlette UploadFile](https://www.starlette.io/requests/#request-files)
- [MDN: Sending form data](https://developer.mozilla.org/en-US/docs/Learn/Forms/Sending_and_retrieving_form_data)
