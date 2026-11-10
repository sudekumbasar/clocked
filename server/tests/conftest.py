import io

import pytest
from PIL import Image


def make_photo(size=(2400, 1800), colour=(200, 30, 30), with_gps=True, fmt="JPEG") -> bytes:
    image = Image.new("RGB", size, colour)
    exif = Image.Exif()
    if with_gps:
        exif[0x010E] = "test photo"  # ImageDescription
        exif[0x8825] = {1: "N", 2: (51.0, 30.0, 47.0), 3: "W", 4: (0.0, 8.0, 45.0)}  # GPS
    out = io.BytesIO()
    image.save(out, format=fmt, exif=exif)
    return out.getvalue()


@pytest.fixture
def photo() -> bytes:
    return make_photo()
