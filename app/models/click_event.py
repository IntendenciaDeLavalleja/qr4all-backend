import hashlib
from datetime import datetime, timezone
from ..extensions import db


def _hash_ip(ip: str, salt: str) -> str:
    raw = f"{salt}:{ip}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _anonymize_ip(ip: str) -> str:
    if not ip:
        return None
    if '.' in ip:
        parts = ip.split('.')
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.{parts[2]}.0"
    if ':' in ip:
        segments = ip.split(':')
        if len(segments) >= 4:
            return ':'.join(segments[:4]) + '::'
    return ip


class ClickEvent(db.Model):
    __tablename__ = 'click_events'

    id = db.Column(db.Integer, primary_key=True)
    link_id = db.Column(
        db.Integer, db.ForeignKey('links.id', ondelete='CASCADE'), nullable=False, index=True
    )
    qr_code_id = db.Column(
        db.Integer, db.ForeignKey('qr_codes.id', ondelete='SET NULL'), nullable=True, index=True
    )
    timestamp = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )
    ip_hash = db.Column(db.String(64), nullable=True, index=True)
    ip_anonymized = db.Column(db.String(45), nullable=True)
    user_agent_raw = db.Column(db.Text, nullable=True)
    browser = db.Column(db.String(80), nullable=True, index=True)
    browser_version = db.Column(db.String(80), nullable=True)
    os = db.Column(db.String(80), nullable=True, index=True)
    os_version = db.Column(db.String(80), nullable=True)
    device_type = db.Column(db.String(40), nullable=True, index=True)
    device_family = db.Column(db.String(120), nullable=True)
    referrer = db.Column(db.Text, nullable=True)
    accept_language = db.Column(db.String(255), nullable=True)
    primary_language = db.Column(db.String(20), nullable=True, index=True)
    method = db.Column(db.String(10), nullable=True)
    path = db.Column(db.String(255), nullable=True)
    status_code = db.Column(db.Integer, nullable=True)
    is_bot = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    link = db.relationship('Link', back_populates='click_events')
    qr_code = db.relationship('QrCode', back_populates='click_events')

    @staticmethod
    def from_request(link_id, qr_code_id, request_obj, ip_salt, status_code=302):
        ua_string = request_obj.headers.get('User-Agent', '')
        raw_ip = request_obj.remote_addr or ''

        browser = browser_version = os_name = os_version = device_type = device_family = None
        is_bot = False

        try:
            from user_agents import parse as parse_ua
            ua = parse_ua(ua_string)
            browser = ua.browser.family
            browser_version = ua.browser.version_string
            os_name = ua.os.family
            os_version = ua.os.version_string
            device_type = 'mobile' if ua.is_mobile else 'tablet' if ua.is_tablet else 'bot' if ua.is_bot else 'desktop'
            device_family = ua.device.family
            is_bot = ua.is_bot
        except Exception:
            if ua_string:
                ua_lower = ua_string.lower()
                if any(b in ua_lower for b in ('bot', 'crawler', 'spider', 'curl', 'wget')):
                    is_bot = True
                    device_type = 'bot'

        referrer = request_obj.referrer
        accept_lang = request_obj.headers.get('Accept-Language', '')
        primary_lang = None
        if accept_lang:
            primary_lang = accept_lang.split(',')[0].strip().split(';')[0].strip()[:20]

        return ClickEvent(
            link_id=link_id,
            qr_code_id=qr_code_id,
            ip_hash=_hash_ip(raw_ip, ip_salt) if raw_ip else None,
            ip_anonymized=_anonymize_ip(raw_ip),
            user_agent_raw=ua_string[:2000] if ua_string else None,
            browser=browser,
            browser_version=browser_version,
            os=os_name,
            os_version=os_version,
            device_type=device_type,
            device_family=device_family,
            referrer=referrer[:2000] if referrer else None,
            accept_language=accept_lang[:255] if accept_lang else None,
            primary_language=primary_lang,
            method=request_obj.method,
            path=request_obj.path[:255],
            status_code=status_code,
            is_bot=is_bot,
        )

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'link_id': self.link_id,
            'qr_code_id': self.qr_code_id,
            'timestamp': self.timestamp.isoformat(),
            'browser': self.browser,
            'browser_version': self.browser_version,
            'os': self.os,
            'os_version': self.os_version,
            'device_type': self.device_type,
            'device_family': self.device_family,
            'referrer': self.referrer,
            'primary_language': self.primary_language,
            'is_bot': self.is_bot,
            'status_code': self.status_code,
        }

    def __repr__(self) -> str:
        return f'<ClickEvent link={self.link_id} ts={self.timestamp}>'
