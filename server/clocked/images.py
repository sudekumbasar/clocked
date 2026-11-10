"""Prepare an uploaded photo for the vision model.

The photo is re-encoded as a JPEG with no metadata, so the GPS position a phone
stores inside a photo is never sent to the model provider.
"""

from __future__ import annotations

import io

from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener

register_heif_opener()

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_LONG_EDGE = 1568
JPEG_QUALITY = 85


class ImageError(ValueError):
    """The upload is not a usable photo."""


def prepare(data: bytes) -> tuple[bytes, str]:
    """Return (jpeg bytes, media type), upright, downscaled and stripped of metadata."""
    if not data:
        raise ImageError("the photo is empty")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ImageError("the photo is too large")
    try:
        with Image.open(io.BytesIO(data)) as image:
            image = ImageOps.exif_transpose(image)
            image = image.convert("RGB")
    except (UnidentifiedImageError, OSError) as error:
        raise ImageError("the upload is not a photo") from error

    image.thumbnail((MAX_LONG_EDGE, MAX_LONG_EDGE))
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=JPEG_QUALITY)  # no exif= argument: metadata dropped
    return out.getvalue(), "image/jpeg"
