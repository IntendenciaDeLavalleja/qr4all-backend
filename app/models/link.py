import re
import secrets
import string
from datetime import datetime, timezone
from ..extensions import db

RESERVED_SLUGS = frozenset({
    'api', 'admin', 'login', 'verify-2fa', 'dashboard', 'links',
    'analytics', 'settings', 'health', 'r', 'static', 'assets',
    'favicon.ico', 'favicon.svg',
})

_SLUG_RE = re.compile(r'^[A-Za-z0-9_-]+$')
_ALPHABET = string.ascii_letters + string.digits


def _generate_slug(length: int = 7) -> str:
    return ''.join(secrets.choice(_ALPHABET) for _ in range(length))


class Link(db.Model):
    __tablename__ = 'links'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=True)
    original_url = db.Column(db.Text, nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    campaign = db.Column(db.String(120), nullable=True, index=True)
    category = db.Column(db.String(120), nullable=True, index=True)
    location_name = db.Column(db.String(160), nullable=True)
    locality = db.Column(db.String(120), nullable=True, index=True)
    placement_type = db.Column(db.String(80), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    click_count = db.Column(db.Integer, default=0, nullable=False, index=True)
    last_accessed_at = db.Column(db.DateTime, nullable=True)
    created_by_id = db.Column(
        db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True
    )
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    creator = db.relationship('User', foreign_keys=[created_by_id], lazy='select')
    click_events = db.relationship(
        'ClickEvent', back_populates='link', cascade='all, delete-orphan', lazy='dynamic'
    )
    qr_codes = db.relationship(
        'QrCode', back_populates='link', cascade='all, delete-orphan', lazy='dynamic'
    )

    @staticmethod
    def generate_unique_slug(max_attempts: int = 10) -> str:
        for _ in range(max_attempts):
            slug = _generate_slug()
            if slug.lower() not in RESERVED_SLUGS:
                if not Link.query.filter_by(slug=slug).first():
                    return slug
        raise ValueError("Could not generate unique slug")

    def short_url(self, base_url: str) -> str:
        return f"{base_url.rstrip('/')}/r/{self.slug}"

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'original_url': self.original_url,
            'slug': self.slug,
            'campaign': self.campaign,
            'category': self.category,
            'location_name': self.location_name,
            'locality': self.locality,
            'placement_type': self.placement_type,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'is_active': self.is_active,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'click_count': self.click_count,
            'last_accessed_at': self.last_accessed_at.isoformat() if self.last_accessed_at else None,
            'created_by_id': self.created_by_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }

    def to_detail_dict(self, base_url: str) -> dict:
        d = self.to_dict()
        d['short_url'] = self.short_url(base_url)
        return d

    def __repr__(self) -> str:
        return f'<Link {self.slug} -> {self.original_url[:50]}>'
