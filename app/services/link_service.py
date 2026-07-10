import re
from flask import current_app
from ..extensions import db
from ..models import Link
from ..models.link import RESERVED_SLUGS, _SLUG_RE
from .url_validator import validate_url, normalize_url


def _clean_coord(value, name: str, lo: float, hi: float) -> float | None:
    """Normalize a coordinate value to float | None.

    Accepts numbers, numeric strings, empty strings and None.
    Empty/None -> None. Invalid or out-of-range -> ValueError.
    """
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} debe ser un número válido.")
    if num < lo or num > hi:
        raise ValueError(f"{name} debe estar entre {lo} y {hi}.")
    return num


def create_link(data: dict, user_id: int | None = None) -> Link:
    title = (data.get('title') or '').strip()
    original_url = (data.get('original_url') or '').strip()

    if not title:
        raise ValueError("El título es requerido.")
    if not original_url:
        raise ValueError("La URL de destino es requerida.")

    original_url = normalize_url(original_url)
    valid, error = validate_url(original_url)
    if not valid:
        raise ValueError(error)

    custom_slug = (data.get('custom_slug') or '').strip()
    if custom_slug:
        if not _SLUG_RE.match(custom_slug):
            raise ValueError("El slug solo puede contener letras, números, guión y guión bajo.")
        if len(custom_slug) > 80:
            raise ValueError("El slug no puede tener más de 80 caracteres.")
        if custom_slug.lower() in RESERVED_SLUGS:
            raise ValueError(f"'{custom_slug}' es un slug reservado.")
        if Link.query.filter_by(slug=custom_slug).first():
            raise ValueError(f"El slug '{custom_slug}' ya existe.")
        slug = custom_slug
    else:
        slug = Link.generate_unique_slug()

    link = Link(
        title=title,
        description=(data.get('description') or '').strip() or None,
        original_url=original_url,
        slug=slug,
        campaign=(data.get('campaign') or '').strip() or None,
        category=(data.get('category') or '').strip() or None,
        location_name=(data.get('location_name') or '').strip() or None,
        locality=(data.get('locality') or '').strip() or None,
        placement_type=(data.get('placement_type') or '').strip() or None,
        latitude=_clean_coord(data.get('latitude'), 'latitude', -90.0, 90.0),
        longitude=_clean_coord(data.get('longitude'), 'longitude', -180.0, 180.0),
        expires_at=data.get('expires_at'),
        created_by_id=user_id,
    )
    db.session.add(link)
    db.session.commit()
    return link


def update_link(link: Link, data: dict) -> Link:
    if 'title' in data:
        title = (data['title'] or '').strip()
        if not title:
            raise ValueError("El título no puede estar vacío.")
        link.title = title

    if 'description' in data:
        link.description = (data['description'] or '').strip() or None

    if 'original_url' in data:
        url = (data['original_url'] or '').strip()
        if url:
            url = normalize_url(url)
            valid, error = validate_url(url)
            if not valid:
                raise ValueError(error)
            link.original_url = url

    for field in ('campaign', 'category', 'location_name', 'locality', 'placement_type'):
        if field in data:
            setattr(link, field, (data[field] or '').strip() or None)

    if 'latitude' in data:
        link.latitude = _clean_coord(data['latitude'], 'latitude', -90.0, 90.0)
    if 'longitude' in data:
        link.longitude = _clean_coord(data['longitude'], 'longitude', -180.0, 180.0)

    if 'is_active' in data:
        link.is_active = bool(data['is_active'])

    if 'expires_at' in data:
        link.expires_at = data['expires_at']

    db.session.commit()
    return link


def soft_delete_link(link: Link) -> Link:
    link.is_active = False
    db.session.commit()
    return link
