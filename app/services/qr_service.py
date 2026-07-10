import io
import os
import re
import uuid
from flask import current_app
from PIL import Image
from ..extensions import db
from ..models import QrCode

_EC_LEVELS = {
    'L': 'L',
    'M': 'M',
    'Q': 'Q',
    'H': 'H',
}

_COLOR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')


def _validate_color(color: str, default: str) -> str:
    if not color:
        return default
    color = color.strip()
    if _COLOR_RE.match(color):
        return color
    return default


def _safe_ext(mime: str | None) -> str:
    if mime == 'image/png':
        return 'png'
    if mime in ('image/jpeg', 'image/jpg'):
        return 'jpg'
    if mime == 'image/webp':
        return 'webp'
    return 'png'


def _validate_logo_file(file_storage) -> tuple[bytes, str, str]:
    """Validate uploaded logo and return (bytes, mime_type, ext)."""
    if not file_storage or not file_storage.filename:
        raise ValueError("No se proporcionó ningún archivo de logo.")

    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)

    max_size = current_app.config.get('QR_LOGO_MAX_SIZE_BYTES', 2 * 1024 * 1024)
    if size > max_size:
        raise ValueError(
            f"El logo excede el tamaño máximo permitido de "
            f"{max_size // (1024 * 1024)} MB."
        )

    mime = file_storage.mimetype or ''
    allowed = current_app.config.get(
        'QR_LOGO_ALLOWED_MIMETYPES',
        {'image/png', 'image/jpeg', 'image/webp'},
    )
    if mime not in allowed:
        raise ValueError("Formato de imagen no permitido. Usá PNG, JPEG o WEBP.")

    data = file_storage.read()
    try:
        img = Image.open(io.BytesIO(data))
        img.verify()
    except Exception as exc:
        raise ValueError("El archivo no es una imagen válida.") from exc

    return data, mime, _safe_ext(mime)


def _upload_logo_to_storage(data: bytes, ext: str, link_id: int) -> str:
    """Upload logo bytes to MinIO. Returns the object key.

    DEPRECATED: kept only for legacy fallback paths. New code should use
    media_service.upload_asset() which creates a MediaAsset record and
    deduplicates by checksum.
    """
    from .storage import storage_service

    object_key = storage_service.build_logo_key(link_id, ext)
    content_type = f"image/{'jpeg' if ext == 'jpg' else ext}"
    storage_service.upload_bytes(data, object_key, content_type)
    return object_key


def _get_logo_bytes(qr: 'QrCode') -> bytes | None:
    """Retrieve logo bytes: prefer MinIO (object_key), fall back to local file."""
    if qr.logo_object_key:
        from .storage import storage_service
        return storage_service.get_object_bytes(qr.logo_object_key)

    if qr.logo_path and os.path.exists(qr.logo_path):
        try:
            with open(qr.logo_path, 'rb') as f:
                return f.read()
        except Exception:
            return None

    return None


def _open_rgba_logo(logo_bytes: bytes, target_size: int) -> Image.Image:
    img = Image.open(io.BytesIO(logo_bytes)).convert('RGBA')
    img = img.resize((target_size, target_size), Image.Resampling.LANCZOS)
    return img


def _compose_logo_onto_qr(qr_img: Image.Image, logo: Image.Image) -> Image.Image:
    """Paste logo centered on QR with a light rounded padding behind it."""
    qr_size = qr_img.size[0]
    logo_size = logo.size[0]

    padding = max(4, int(logo_size * 0.12))
    bg_size = logo_size + padding * 2
    bg = Image.new('RGBA', (bg_size, bg_size), (255, 255, 255, 255))
    corner = int(bg_size * 0.18)
    mask = Image.new('L', (bg_size, bg_size), 0)
    from PIL import ImageDraw
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, bg_size, bg_size), radius=corner, fill=255)
    bg.putalpha(mask)

    composite = qr_img.convert('RGBA').copy()
    bg_pos = ((qr_size - bg_size) // 2, (qr_size - bg_size) // 2)
    logo_pos = ((qr_size - logo_size) // 2, (qr_size - logo_size) // 2)

    composite.paste(bg, bg_pos, bg)
    composite.paste(logo, logo_pos, logo)
    return composite


def generate_qr_image(
    url: str,
    fmt: str = 'png',
    size: int = 512,
    fill_color: str = '#000000',
    back_color: str = '#ffffff',
    error_correction: str = 'M',
    logo_path: str | None = None,
    qr: 'QrCode | None' = None,
) -> tuple[bytes, str]:
    """Generate QR image bytes. If `qr` is provided, uses its logo from MinIO/local."""
    import qrcode
    from qrcode.constants import (
        ERROR_CORRECT_L,
        ERROR_CORRECT_M,
        ERROR_CORRECT_Q,
        ERROR_CORRECT_H,
    )

    ec_map = {
        'L': ERROR_CORRECT_L,
        'M': ERROR_CORRECT_M,
        'Q': ERROR_CORRECT_Q,
        'H': ERROR_CORRECT_H,
    }

    fill_color = _validate_color(fill_color, '#000000')
    back_color = _validate_color(back_color, '#ffffff')

    # Determine if we have a logo
    logo_bytes = None
    if qr and (qr.logo_object_key or qr.logo_path):
        logo_bytes = _get_logo_bytes(qr)
    elif logo_path and os.path.exists(logo_path):
        with open(logo_path, 'rb') as f:
            logo_bytes = f.read()

    has_logo = bool(logo_bytes)
    requested_ec = error_correction.upper() if error_correction.upper() in _EC_LEVELS else 'M'
    ec_level = ec_map.get(requested_ec if not has_logo else 'H', ERROR_CORRECT_M)

    box_size = max(1, size // 25)
    border = 2

    qr_obj = qrcode.QRCode(
        version=None,
        error_correction=ec_level,
        box_size=box_size,
        border=border,
    )
    qr_obj.add_data(url)
    qr_obj.make(fit=True)

    if fmt.lower() == 'svg':
        import qrcode.image.svg as svg_mod
        factory = svg_mod.SvgPathImage
        img = qr_obj.make_image(
            image_factory=factory,
            fill_color=fill_color,
            back_color=back_color,
        )
        buf = io.BytesIO()
        img.save(buf)
        return buf.getvalue(), 'image/svg+xml'
    else:
        img = qr_obj.make_image(fill_color=fill_color, back_color=back_color)
        img = img.resize((size, size))

        if has_logo:
            logo_target_size = int(size * 0.20)
            logo = _open_rgba_logo(logo_bytes, logo_target_size)
            img = _compose_logo_onto_qr(img, logo)

        buf = io.BytesIO()
        final = img.convert('RGBA') if has_logo else img.convert('RGB')
        final.save(buf, format='PNG')
        return buf.getvalue(), 'image/png'


def create_qr_record(
    link_id: int,
    generated_url: str,
    name: str | None = None,
    fmt: str = 'png',
    size: int = 512,
    fill_color: str = '#000000',
    back_color: str = '#ffffff',
    error_correction: str = 'M',
    logo_file=None,
    logo_asset=None,
    created_by_id: int | None = None,
) -> QrCode:
    """Create a QR record with an optional logo.

    Exactly one of `logo_file` or `logo_asset` may be provided.
    `logo_file` creates/reuses a MediaAsset via media_service (dedup by
    checksum, stable object key). `logo_asset` reuses an existing
    MediaAsset without uploading.
    """
    from . import media_service

    logo_object_key = None
    logo_original_name = None
    logo_mime_type = None
    logo_asset_id = None

    if logo_file and logo_asset is not None:
        raise ValueError(
            'Elegí subir una imagen nueva o seleccionar una existente, no ambas.'
        )

    new_asset_uploaded = False
    if logo_file:
        # media_service.upload_asset handles validation, dedup, upload,
        # and DB record creation. Re-uploaded identical images reuse the
        # existing MediaAsset (no duplicate MinIO object).
        asset = media_service.upload_asset(
            file_storage=logo_file,
            category='qr_logo',
            created_by_id=created_by_id,
        )
        logo_object_key = asset.object_key
        logo_original_name = asset.original_filename or asset.name
        logo_mime_type = asset.content_type
        logo_asset_id = asset.id
        new_asset_uploaded = True

    if logo_asset is not None:
        if not logo_asset.is_active:
            raise ValueError('La imagen seleccionada no está disponible.')
        if logo_asset.category != 'qr_logo':
            raise ValueError('La imagen seleccionada no es un logo válido.')
        logo_object_key = logo_asset.object_key
        logo_original_name = logo_asset.original_filename or logo_asset.name
        logo_mime_type = logo_asset.content_type
        logo_asset_id = logo_asset.id

    qr = QrCode(
        link_id=link_id,
        name=name,
        format=fmt,
        size=size,
        fill_color=_validate_color(fill_color, '#000000'),
        back_color=_validate_color(back_color, '#ffffff'),
        error_correction=error_correction.upper() if error_correction.upper() in _EC_LEVELS else 'M',
        generated_url=generated_url,
        has_logo=bool(logo_object_key),
        logo_object_key=logo_object_key,
        logo_original_name=logo_original_name,
        logo_mime_type=logo_mime_type,
        logo_asset_id=logo_asset_id,
    )
    db.session.add(qr)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        # If a newly created MediaAsset was used (deduped or fresh upload)
        # and the QR DB insert failed, the asset is left in the library —
        # it's harmless to have unused library assets, and avoids destroying
        # an asset that might be referenced by another QR or future upload.
        # The user can clean unused assets manually via the admin UI.
        current_app.logger.exception(
            'QR creation failed for link %s; media asset %s left in library',
            link_id, logo_asset_id,
        )
        raise
    return qr


def delete_qr_logo(qr: 'QrCode'):
    """Delete logo from storage if present. Safe to call even if no logo."""
    if not qr.logo_object_key:
        return
    try:
        from .storage import storage_service
        storage_service.delete_object(qr.logo_object_key)
    except Exception as exc:
        current_app.logger.warning(
            "Failed to delete logo '%s': %s", qr.logo_object_key, exc,
        )
    qr.logo_object_key = None
    qr.has_logo = False
    db.session.commit()


def get_logo_url(qr: 'QrCode') -> str | None:
    """Return a URL for the QR logo, or None if no logo."""
    if not qr.logo_object_key:
        return None
    try:
        from .storage import storage_service
        return storage_service.get_object_url(qr.logo_object_key)
    except Exception:
        return None