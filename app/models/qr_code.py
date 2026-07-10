from datetime import datetime, timezone
from ..extensions import db


class QrCode(db.Model):
    __tablename__ = 'qr_codes'

    id = db.Column(db.Integer, primary_key=True)
    link_id = db.Column(
        db.Integer, db.ForeignKey('links.id', ondelete='CASCADE'), nullable=False, index=True
    )
    name = db.Column(db.String(120), nullable=True)
    format = db.Column(db.String(20), default='png', nullable=False)
    size = db.Column(db.Integer, default=512, nullable=False)
    fill_color = db.Column(db.String(20), default='#000000', nullable=False)
    back_color = db.Column(db.String(20), default='#ffffff', nullable=False)
    error_correction = db.Column(db.String(5), default='M', nullable=False)
    generated_url = db.Column(db.Text, nullable=False)
    has_logo = db.Column(db.Boolean, default=False, nullable=False)
    logo_object_key = db.Column(db.String(255), nullable=True, index=True)
    logo_path = db.Column(db.String(255), nullable=True)
    logo_original_name = db.Column(db.String(200), nullable=True)
    logo_mime_type = db.Column(db.String(100), nullable=True)
    logo_asset_id = db.Column(
        db.Integer,
        db.ForeignKey('media_assets.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    link = db.relationship('Link', back_populates='qr_codes')
    click_events = db.relationship('ClickEvent', back_populates='qr_code', lazy='dynamic')

    def to_dict(self, include_logo_url: bool = False) -> dict:
        d = {
            'id': self.id,
            'link_id': self.link_id,
            'name': self.name,
            'format': self.format,
            'size': self.size,
            'fill_color': self.fill_color,
            'back_color': self.back_color,
            'error_correction': self.error_correction,
            'generated_url': self.generated_url,
            'has_logo': self.has_logo,
            'logo_original_name': self.logo_original_name,
            'logo_mime_type': self.logo_mime_type,
            'created_at': self.created_at.isoformat(),
        }
        if include_logo_url and self.logo_object_key:
            from ..services.qr_service import get_logo_url
            d['logo_url'] = get_logo_url(self)
        return d

    def __repr__(self) -> str:
        return f'<QrCode link={self.link_id} fmt={self.format}>'
