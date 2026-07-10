from datetime import datetime, timezone, timedelta
from sqlalchemy import func, case, extract
from ..extensions import db
from ..models import Link, ClickEvent, QrCode


def record_click(
    link: Link,
    request_obj,
    ip_salt: str,
    qr_code_id: int | None = None,
) -> ClickEvent | None:
    try:
        event = ClickEvent.from_request(
            link_id=link.id,
            qr_code_id=qr_code_id,
            request_obj=request_obj,
            ip_salt=ip_salt,
        )
        db.session.add(event)
        link.click_count = Link.click_count + 1
        link.last_accessed_at = datetime.now(timezone.utc)
        db.session.commit()
        return event
    except Exception as exc:
        db.session.rollback()
        try:
            current_app = request_obj.environ.get('flask.app')
            if current_app:
                current_app.logger.error(f"Analytics recording failed: {exc}")
        except Exception:
            pass
        return None


def _parse_range(range_str: str | None) -> int:
    if not range_str:
        return 30
    mapping = {'7d': 7, '30d': 30, '90d': 90, '365d': 365}
    return mapping.get(range_str, 30)


def _start_date(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def get_overview() -> dict:
    total_links = Link.query.count()
    active_links = Link.query.filter_by(is_active=True).count()
    total_clicks = db.session.query(func.sum(Link.click_count)).scalar() or 0

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    clicks_today = ClickEvent.query.filter(ClickEvent.timestamp >= today_start).count()
    clicks_7d = ClickEvent.query.filter(ClickEvent.timestamp >= _start_date(7)).count()
    clicks_30d = ClickEvent.query.filter(ClickEvent.timestamp >= _start_date(30)).count()

    top_link = Link.query.order_by(Link.click_count.desc()).first()
    top_link_dict = None
    if top_link:
        top_link_dict = {
            'id': top_link.id,
            'title': top_link.title,
            'slug': top_link.slug,
            'click_count': top_link.click_count,
        }

    most_recent = db.session.query(func.max(ClickEvent.timestamp)).scalar()

    return {
        'total_links': total_links,
        'active_links': active_links,
        'total_clicks': total_clicks,
        'clicks_today': clicks_today,
        'clicks_last_7_days': clicks_7d,
        'clicks_last_30_days': clicks_30d,
        'top_link': top_link_dict,
        'most_recent_click_at': most_recent.isoformat() if most_recent else None,
    }


def get_timeseries(range_str: str | None = '30d', link_id: int | None = None) -> list[dict]:
    days = _parse_range(range_str)
    start = _start_date(days)

    query = db.session.query(
        func.date(ClickEvent.timestamp).label('date'),
        func.count(ClickEvent.id).label('count'),
    ).filter(ClickEvent.timestamp >= start)

    if link_id:
        query = query.filter(ClickEvent.link_id == link_id)

    rows = query.group_by(func.date(ClickEvent.timestamp)).order_by('date').all()
    return [{'date': str(r.date), 'count': r.count} for r in rows]


def get_top_links(range_str: str | None = '30d', limit: int = 10) -> list[dict]:
    days = _parse_range(range_str)
    start = _start_date(days)

    rows = db.session.query(
        Link.id,
        Link.title,
        Link.slug,
        func.count(ClickEvent.id).label('clicks'),
    ).join(ClickEvent, ClickEvent.link_id == Link.id).filter(
        ClickEvent.timestamp >= start
    ).group_by(Link.id, Link.title, Link.slug).order_by(
        func.count(ClickEvent.id).desc()
    ).limit(limit).all()

    return [{'id': r.id, 'title': r.title, 'slug': r.slug, 'clicks': r.clicks} for r in rows]


def get_device_breakdown(range_str: str | None = '30d', link_id: int | None = None) -> list[dict]:
    days = _parse_range(range_str)
    start = _start_date(days)

    query = db.session.query(
        func.coalesce(ClickEvent.device_type, 'unknown').label('device_type'),
        func.count(ClickEvent.id).label('count'),
    ).filter(ClickEvent.timestamp >= start)

    if link_id:
        query = query.filter(ClickEvent.link_id == link_id)

    rows = query.group_by('device_type').order_by(func.count(ClickEvent.id).desc()).all()
    return [{'device_type': r.device_type, 'count': r.count} for r in rows]


def get_browser_breakdown(range_str: str | None = '30d', link_id: int | None = None) -> list[dict]:
    days = _parse_range(range_str)
    start = _start_date(days)

    query = db.session.query(
        func.coalesce(ClickEvent.browser, 'unknown').label('browser'),
        func.count(ClickEvent.id).label('count'),
    ).filter(ClickEvent.timestamp >= start)

    if link_id:
        query = query.filter(ClickEvent.link_id == link_id)

    rows = query.group_by('browser').order_by(func.count(ClickEvent.id).desc()).limit(10).all()
    return [{'browser': r.browser, 'count': r.count} for r in rows]


def get_os_breakdown(range_str: str | None = '30d', link_id: int | None = None) -> list[dict]:
    days = _parse_range(range_str)
    start = _start_date(days)

    query = db.session.query(
        func.coalesce(ClickEvent.os, 'unknown').label('os'),
        func.count(ClickEvent.id).label('count'),
    ).filter(ClickEvent.timestamp >= start)

    if link_id:
        query = query.filter(ClickEvent.link_id == link_id)

    rows = query.group_by('os').order_by(func.count(ClickEvent.id).desc()).limit(10).all()
    return [{'os': r.os, 'count': r.count} for r in rows]


def get_referrers(range_str: str | None = '30d', link_id: int | None = None) -> list[dict]:
    days = _parse_range(range_str)
    start = _start_date(days)

    query = db.session.query(
        func.coalesce(ClickEvent.referrer, 'directo').label('referrer'),
        func.count(ClickEvent.id).label('count'),
    ).filter(ClickEvent.timestamp >= start)

    if link_id:
        query = query.filter(ClickEvent.link_id == link_id)

    rows = query.group_by('referrer').order_by(func.count(ClickEvent.id).desc()).limit(20).all()
    return [{'referrer': r.referrer, 'count': r.count} for r in rows]


def get_languages(range_str: str | None = '30d', link_id: int | None = None) -> list[dict]:
    days = _parse_range(range_str)
    start = _start_date(days)

    query = db.session.query(
        func.coalesce(ClickEvent.primary_language, 'unknown').label('language'),
        func.count(ClickEvent.id).label('count'),
    ).filter(ClickEvent.timestamp >= start)

    if link_id:
        query = query.filter(ClickEvent.link_id == link_id)

    rows = query.group_by('language').order_by(func.count(ClickEvent.id).desc()).limit(20).all()
    return [{'language': r.language, 'count': r.count} for r in rows]


def get_link_analytics(link_id: int, range_str: str | None = '30d') -> dict:
    link = Link.query.get(link_id)
    if not link:
        return {}

    days = _parse_range(range_str)
    start = _start_date(days)

    clicks_in_range = ClickEvent.query.filter(
        ClickEvent.link_id == link_id,
        ClickEvent.timestamp >= start,
    ).count()

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    clicks_today = ClickEvent.query.filter(
        ClickEvent.link_id == link_id,
        ClickEvent.timestamp >= today_start,
    ).count()

    return {
        'link_id': link.id,
        'total_clicks': link.click_count,
        'clicks_in_range': clicks_in_range,
        'clicks_today': clicks_today,
        'timeseries': get_timeseries(range_str, link_id),
        'devices': get_device_breakdown(range_str, link_id),
        'browsers': get_browser_breakdown(range_str, link_id),
        'referrers': get_referrers(range_str, link_id),
        'languages': get_languages(range_str, link_id),
    }


def get_hourly_breakdown(range_str: str | None = '30d', link_id: int | None = None) -> list[dict]:
    days = _parse_range(range_str)
    start = _start_date(days)

    query = db.session.query(
        extract('hour', ClickEvent.timestamp).label('hour'),
        func.count(ClickEvent.id).label('count'),
    ).filter(ClickEvent.timestamp >= start)

    if link_id:
        query = query.filter(ClickEvent.link_id == link_id)

    rows = query.group_by('hour').order_by('hour').all()
    return [{'hour': int(r.hour), 'count': r.count} for r in rows]


def get_recent_events(limit: int = 20, link_id: int | None = None) -> list[dict]:
    query = ClickEvent.query
    if link_id:
        query = query.filter_by(link_id=link_id)
    events = query.order_by(ClickEvent.timestamp.desc()).limit(limit).all()
    result = []
    for ev in events:
        d = ev.to_dict()
        if ev.link:
            d['link_title'] = ev.link.title
            d['link_slug'] = ev.link.slug
        result.append(d)
    return result
