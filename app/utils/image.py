"""
Image processing utilities.

Provides helper functions for image manipulation,
dimension extraction, and validation.
"""

import io
from pathlib import Path
from typing import BinaryIO

import numpy as np
from PIL import Image


def get_image_dimensions(file: BinaryIO) -> tuple[int, int] | None:
    """
    Get dimensions of an image file.

    Args:
        file: File-like object containing image data

    Returns:
        Tuple of (width, height) or None if not a valid image

    Note:
        The file position is reset to the beginning after reading.
    """
    try:
        # Save current position
        pos = file.tell()

        # Read image
        img = Image.open(file)
        dimensions = img.size  # (width, height)

        # Reset file position
        file.seek(pos)

        return dimensions
    except Exception:
        # Not a valid image or other error
        file.seek(0)
        return None


def get_image_format(file: BinaryIO) -> str | None:
    """
    Detect the format of an image file.

    Args:
        file: File-like object containing image data

    Returns:
        Format string (e.g., 'JPEG', 'PNG') or None if not a valid image
    """
    try:
        pos = file.tell()
        img = Image.open(file)
        fmt = img.format
        file.seek(pos)
        return fmt
    except Exception:
        file.seek(0)
        return None


def validate_image_integrity(file: BinaryIO) -> tuple[bool, str]:
    """
    Validate that a file is a valid, uncorrupted image.

    Args:
        file: File-like object containing image data

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        pos = file.tell()

        # Try to open and verify the image
        img = Image.open(file)
        img.verify()  # Verify image integrity

        # Reset and re-open (verify() invalidates the image object)
        file.seek(pos)

        return True, ""
    except Exception as e:
        file.seek(0)
        return False, f"Invalid or corrupted image: {str(e)}"


def create_thumbnail(
    file: BinaryIO,
    max_size: tuple[int, int] = (256, 256),
) -> bytes:
    """
    Create a thumbnail from an image.

    Args:
        file: File-like object containing image data
        max_size: Maximum dimensions (width, height) for thumbnail

    Returns:
        Thumbnail image as bytes (JPEG format)
    """
    pos = file.tell()

    img = Image.open(file)

    # Convert to RGB if necessary (for JPEG output)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # Create thumbnail (modifies in place)
    img.thumbnail(max_size, Image.Resampling.LANCZOS)

    # Save to bytes
    output = io.BytesIO()
    img.save(output, format="JPEG", quality=85, optimize=True)

    file.seek(pos)

    return output.getvalue()


def resize_image(
    file: BinaryIO,
    width: int | None = None,
    height: int | None = None,
    maintain_aspect: bool = True,
) -> bytes:
    """
    Resize an image to specified dimensions.

    Args:
        file: File-like object containing image data
        width: Target width (None to auto-calculate from height)
        height: Target height (None to auto-calculate from width)
        maintain_aspect: Whether to maintain aspect ratio

    Returns:
        Resized image as bytes (same format as input)
    """
    pos = file.tell()

    img = Image.open(file)
    original_format = img.format or "JPEG"
    original_width, original_height = img.size

    if maintain_aspect:
        if width and not height:
            # Calculate height based on width
            ratio = width / original_width
            height = int(original_height * ratio)
        elif height and not width:
            # Calculate width based on height
            ratio = height / original_height
            width = int(original_width * ratio)
        elif width and height:
            # Fit within bounds while maintaining aspect ratio
            width_ratio = width / original_width
            height_ratio = height / original_height
            ratio = min(width_ratio, height_ratio)
            width = int(original_width * ratio)
            height = int(original_height * ratio)

    if width and height:
        img = img.resize((width, height), Image.Resampling.LANCZOS)

    # Convert RGBA to RGB for JPEG
    if original_format == "JPEG" and img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # Save to bytes
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


def extract_dominant_colors(file: BinaryIO, num_colors: int = 5) -> list[dict]:
    """
    Extract dominant colors from an image.

    Args:
        file: File-like object containing image data
        num_colors: Number of dominant colors to extract

    Returns:
        List of color dictionaries with 'hex' and 'percentage' keys
    """
    from collections import Counter

    pos = file.tell()

    img = Image.open(file)

    # Resize for faster processing
    img.thumbnail((150, 150))

    # Convert to RGB
    if img.mode != "RGB":
        img = img.convert("RGB")

    # Get all pixels
    pixels = list(img.getdata())

    # Quantize colors (reduce to palette)
    quantized = img.quantize(colors=num_colors)
    palette = quantized.getpalette()

    # Count pixel occurrences in quantized image
    quantized_pixels = list(quantized.getdata())
    color_counts = Counter(quantized_pixels)
    total_pixels = len(quantized_pixels)

    # Build result
    colors = []
    for color_index, count in color_counts.most_common(num_colors):
        if palette:
            r = palette[color_index * 3]
            g = palette[color_index * 3 + 1]
            b = palette[color_index * 3 + 2]
            hex_color = f"#{r:02x}{g:02x}{b:02x}"
            percentage = (count / total_pixels) * 100
            colors.append({
                "hex": hex_color,
                "rgb": [r, g, b],
                "percentage": round(percentage, 2),
            })

    file.seek(pos)

    return colors


def color_segment_image(
    file: BinaryIO,
    num_clusters: int = 5,
    output_format: str = "PNG",
) -> tuple[bytes, list[dict]]:
    """
    Segment an image by color using k-means clustering.

    Each pixel is replaced with its cluster center color,
    creating a posterized/segmented effect.

    Args:
        file: File-like object containing image data
        num_clusters: Number of color clusters (2-16)
        output_format: Output image format (PNG or JPEG)

    Returns:
        Tuple of (segmented_image_bytes, cluster_colors)
    """
    from sklearn.cluster import KMeans

    pos = file.tell()

    # Load image
    img = Image.open(file)
    if img.mode != "RGB":
        img = img.convert("RGB")

    # Convert to numpy array
    img_array = np.array(img)
    original_shape = img_array.shape

    # Reshape to list of pixels (N, 3)
    pixels = img_array.reshape(-1, 3)

    # Apply k-means clustering
    kmeans = KMeans(n_clusters=num_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(pixels)
    centers = kmeans.cluster_centers_.astype(np.uint8)

    # Replace each pixel with its cluster center
    segmented_pixels = centers[labels]

    # Reshape back to image dimensions
    segmented_array = segmented_pixels.reshape(original_shape)

    # Convert back to PIL Image
    segmented_img = Image.fromarray(segmented_array)

    # Calculate cluster statistics
    unique, counts = np.unique(labels, return_counts=True)
    total_pixels = len(labels)

    cluster_colors = []
    for cluster_idx in range(num_clusters):
        r, g, b = centers[cluster_idx]
        count = counts[unique == cluster_idx][0] if cluster_idx in unique else 0
        percentage = (count / total_pixels) * 100
        cluster_colors.append({
            "cluster": cluster_idx,
            "hex": f"#{r:02x}{g:02x}{b:02x}",
            "rgb": [int(r), int(g), int(b)],
            "percentage": round(percentage, 2),
            "pixel_count": int(count),
        })

    # Sort by percentage
    cluster_colors.sort(key=lambda x: x["percentage"], reverse=True)

    # Save to bytes
    output = io.BytesIO()
    save_kwargs = {"format": output_format}
    if output_format == "JPEG":
        if segmented_img.mode == "RGBA":
            segmented_img = segmented_img.convert("RGB")
        save_kwargs["quality"] = 90

    segmented_img.save(output, **save_kwargs)

    file.seek(pos)

    return output.getvalue(), cluster_colors
