import hashlib
import io
import logging
import os
from datetime import datetime, timezone

from flask import current_app
from PIL import Image

from ..extensions import db
from ..models import MediaAsset

logger = logging.getLogger(__name__)

CATEGORY_QR_LOGO = 'qr_logo'

_VALID_CATEGORIES = {CATEGORY_QR_LOGO}


def _validate_image_bytes(data: bytes, allowed_mime: set, max_size: int):
    """Validate image bytes. Returns (mime, ext, width, height) or raises ValueError."""
    if not data:
        raise ValueError('El archivo está vacío.')

    if len(data) > max_size:
        raise ValueError(
            f'El archivo excede el tamaño máximo permitido de '
            f'{max_size // (1024 * 1024)} MB.'
        )

    try:
        img = Image.open(io.BytesIO(data))
        img.verify()
    except Exception as exc:
        raise ValueError('El archivo no es una imagen válida.') from exc

    # Re-open to get dimensions (verify() invalidates the file)
    img = Image.open(io.BytesIO(data))
    width, height = img.size
    fmt = (img.format or '').lower()
    ext_map = {'png': 'png', 'jpeg': 'jpg', 'jpg': 'jpg', 'webp': 'webp'}
    ext = ext_map.get(fmt, 'png')
    mime = f'image/{fmt if fmt != "jpg" else "jpeg"}'

    if mime not in allowed_mime:
        raise ValueError(
            'Formato de imagen no permitido. Usá PNG, JPEG o WEBP.'
        )

    return mime, ext, width, height


def _build_object_key(category: str, checksum: str, ext: str) -> str:
    return f'qr4all/media/{category}/{checksum}.{ext}'


def list_assets(
    category: str | None = None,
    include_inactive: bool = False,
) -> list[MediaAsset]:
    query = MediaAsset.query
    if not include_inactive:
        query = query.filter_by(is_active=True)
    if category:
        query = query.filter_by(category=category)
    return query.order_by(MediaAsset.created_at.desc()).all()


def get_asset(asset_id: int) -> MediaAsset | None:
    return db.session.get(MediaAsset, asset_id)


def upload_asset(
    file_storage,
    name: str | None = None,
    category: str = CATEGORY_QR_LOGO,
    created_by_id: int | None = None,
) -> MediaAsset:
    """Validate, dedup by checksum, upload to MinIO, save metadata."""
    from .storage import storage_service

    if not file_storage or not file_storage.filename:
        raise ValueError('No se proporcionó ningún archivo.')

    if category not in _VALID_CATEGORIES:
        raise ValueError(f'Categoría no soportada: {category}')

    # Read the entire file into memory
    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    data = file_storage.read()

    max_size = current_app.config.get('QR_LOGO_MAX_SIZE_BYTES', 2 * 1024 * 1024)
    allowed_mime = current_app.config.get(
        'QR_LOGO_ALLOWED_MIMETYPES',
        {'image/png', 'image/jpeg', 'image/webp'},
    )

    mime, ext, width, height = _validate_image_bytes(
        data, allowed_mime, max_size
    )

    checksum = hashlib.sha256(data).hexdigest()

    # Deduplicate: return existing active asset with same checksum+category
    existing = MediaAsset.query.filter_by(
        checksum_sha256=checksum,
        category=category,
        is_active=True,
    ).first()
    if existing:
        logger.info(
            'Reusing existing media asset id=%s checksum=%s',
            existing.id, checksum[:12],
        )
        return existing

    if not storage_service.available:
        raise RuntimeError('storage_unavailable')

    object_key = _build_object_key(category, checksum, ext)
    content_type = f'image/{"jpeg" if ext == "jpg" else ext}'
    storage_service.upload_bytes(data, object_key, content_type)

    asset = MediaAsset(
        name=(name or file_storage.filename or 'image').strip()[:200],
        description=None,
        object_key=object_key,
        original_filename=(file_storage.filename or '')[:255] or None,
        content_type=content_type,
        size_bytes=len(data),
        width=width,
        height=height,
        checksum_sha256=checksum,
        category=category,
        is_active=True,
        created_by_id=created_by_id,
        created_at=datetime.now(timezone.utc),
    )
    db.session.add(asset)
    db.session.commit()
    logger.info('Created media asset id=%s key=%s', asset.id, object_key)
    return asset


def soft_delete_asset(asset_id: int) -> bool:
    """Soft delete: set is_active=False. Does not touch MinIO object."""
    asset = db.session.get(MediaAsset, asset_id)
    if not asset:
        return False
    asset.is_active = False
    asset.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return True


def get_asset_url(asset: MediaAsset) -> str | None:
    if not asset or not asset.object_key:
        return None
    from .storage import storage_service
    try:
        return storage_service.get_object_url(asset.object_key)
    except Exception:
        return None