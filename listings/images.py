import logging
from io import BytesIO
from pathlib import PurePosixPath

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

logger = logging.getLogger(__name__)

MAX_SIDE = 1920
THUMB_SIDE = 640
QUALITY = 80
THUMB_QUALITY = 74


def _encode_webp(image: Image.Image, max_side: int, quality: int) -> bytes:
    copy = image.copy()
    copy.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    buffer = BytesIO()
    copy.save(buffer, format="WEBP", quality=quality, method=6)
    return buffer.getvalue()


def _load(file_obj) -> Image.Image:
    file_obj.seek(0)
    image = Image.open(file_obj)
    image = ImageOps.exif_transpose(image)
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
    return image


def build_webp_pair(file_obj, original_name: str) -> tuple[ContentFile, ContentFile] | None:
    """Return (full-size WebP, thumbnail WebP) or None if the file is not a readable image."""
    try:
        image = _load(file_obj)
        full = _encode_webp(image, MAX_SIDE, QUALITY)
        thumb = _encode_webp(image, THUMB_SIDE, THUMB_QUALITY)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        logger.warning("Image optimization skipped for %s: %s", original_name, exc)
        return None

    stem = PurePosixPath(original_name).stem or "image"
    return ContentFile(full, name=f"{stem}.webp"), ContentFile(thumb, name=f"{stem}-thumb.webp")


def optimize_upload(field_file):
    name = PurePosixPath(field_file.name or "image").name
    return build_webp_pair(field_file, name)


def optimize_stored(property_image) -> bool:
    """Convert an already-saved PropertyImage to WebP + thumbnail. Returns True if changed."""
    if not property_image.image:
        return False
    is_webp = property_image.image.name.lower().endswith(".webp")
    if is_webp and property_image.thumbnail:
        return False

    try:
        with property_image.image.open("rb") as handle:
            pair = build_webp_pair(handle, PurePosixPath(property_image.image.name).name)
    except FileNotFoundError:
        return False
    if pair is None:
        return False

    full, thumb = pair
    old_image = property_image.image.name if not is_webp else None
    old_thumb = property_image.thumbnail.name if property_image.thumbnail else None
    storage = property_image.image.storage

    if not is_webp:
        property_image.image.save(full.name, full, save=False)
    property_image.thumbnail.save(thumb.name, thumb, save=False)
    type(property_image).objects.filter(pk=property_image.pk).update(
        image=property_image.image.name,
        thumbnail=property_image.thumbnail.name,
    )

    for name in (old_image, old_thumb):
        if name and name not in (property_image.image.name, property_image.thumbnail.name):
            storage.delete(name)
    return True
