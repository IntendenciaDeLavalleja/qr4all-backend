from datetime import datetime, timezone
from ..extensions import db


class MediaAsset(db.Model):
    __tablename__ = 'media_assets'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    object_key = db.Column(db.String(255), nullable=False, index=True)
    original_filename = db.Column(db.String(255), nullable=True)
    content_type = db.Column(db.String(100), nullable=False)
    size_bytes = db.Column(db.Integer, nullable=False, default=0)
    width = db.Column(db.Integer, nullable=True)
    height = db.Column(db.Integer, nullable=True)
    checksum_sha256 = db.Column(db.String(64), nullable=False, index=True)
    category = db.Column(
        db.String(64), nullable=False, default='qr_logo', index=True
    )
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_by_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
    )
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=True,
    )

    creator = db.relationship('User', foreign_keys=[created_by_id])

    def to_dict(self, include_preview_url: bool = True) -> dict:
        d = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'original_filename': self.original_filename,
            'content_type': self.content_type,
            'size_bytes': self.size_bytes,
            'width': self.width,
            'height': self.height,
            'category': self.category,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_preview_url:
            try:
                from ..services.storage import storage_service
                d['preview_url'] = storage_service.get_object_url(self.object_key)
            except Exception:
                d['preview_url'] = None
        return d

    def __repr__(self) -> str:
        return f'<MediaAsset id={self.id} name={self.name!r} category={self.category}>'