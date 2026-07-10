"""
CLI commands for QR4All Lavalleja.
Usage:
  flask create-admin <name> <email> <password> <is_super_admin>
  flask init-db
  flask seed-qr-demo
  flask seed-analytics-dummy
  flask repair-alembic
"""
import click
from flask.cli import with_appcontext

from .extensions import db


# ─── create-admin ─────────────────────────────────────────────────────────────

@click.command('create-admin')
@click.argument('name')
@click.argument('email')
@click.argument('password')
@click.argument('super_admin', default='false')
@with_appcontext
def create_admin(name: str, email: str, password: str, super_admin: str):
    """Create an admin user. SUPER_ADMIN: true or false."""
    from .models import User
    from .utils.email_validation import normalize_and_validate_email

    try:
        email = normalize_and_validate_email(email)
    except ValueError:
        click.echo(f'[!] Invalid email format: "{email}". Use a valid email like admin@example.com')
        return

    is_super = super_admin.strip().lower() in ('true', '1', 'yes')
    role = 'super_admin' if is_super else 'admin'

    existing = User.query.filter_by(email=email).first()
    if existing:
        click.echo(f'[!] User with email "{email}" already exists.')
        return

    user = User(name=name, email=email, role=role, is_active=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    click.echo(
        f'[+] {role} user "{name}" <{email}> created (id={user.id}).'
    )


# ─── init-db ──────────────────────────────────────────────────────────────────

@click.command('init-db')
@with_appcontext
def init_db():
    """Create all database tables (development only)."""
    db.create_all()
    click.echo('[+] Database tables created.')


# ─── seed-qr-demo ─────────────────────────────────────────────────────────────

@click.command('seed-qr-demo')
@with_appcontext
def seed_demo():
    """Seed the database with demo data for QR4All Lavalleja."""
    from .models import User, Link

    # Admin user
    if not User.query.filter_by(email='admin@lavalleja.uy').first():
        admin = User(
            name='Admin QR4All',
            email='admin@lavalleja.uy',
            role='admin',
            is_active=True,
        )
        admin.set_password('Admin1234!')
        db.session.add(admin)
        click.echo('[+] Admin user created: admin@lavalleja.uy / Admin1234!')

    sample_links = [
        {
            'title': 'Encuesta Turismo Villa Serrana',
            'description': 'Formulario de consulta para visitantes de Villa Serrana',
            'original_url': 'https://forms.google.com/d/e/example1/viewform',
            'slug': 'villa-serrana',
            'campaign': 'Turismo 2026',
            'category': 'Turismo',
            'location_name': 'Oficina de Turismo Villa Serrana',
            'locality': 'Villa Serrana',
            'placement_type': 'cartel',
        },
        {
            'title': 'Inscripciones Biblioteca Municipal',
            'description': 'Formulario de inscripcion para nuevos socios',
            'original_url': 'https://forms.google.com/d/e/example2/viewform',
            'slug': 'biblio-inscripcion',
            'campaign': 'Cultura 2026',
            'category': 'Cultura',
            'location_name': 'Biblioteca Municipal',
            'locality': 'Minas',
            'placement_type': 'oficina',
        },
        {
            'title': 'Relevamiento Areas Verdes',
            'description': 'Encuesta para relevar estado de areas verdes',
            'original_url': 'https://forms.google.com/d/e/example3/viewform',
            'slug': 'areas-verdes',
            'campaign': 'Medio Ambiente',
            'category': 'Medio Ambiente',
            'location_name': 'Parque Artigas',
            'locality': 'Minas',
            'placement_type': 'cartel',
        },
        {
            'title': 'Agenda Cultural Junio',
            'description': 'Calendario de eventos culturales del mes',
            'original_url': 'https://calendar.google.com/example',
            'slug': 'agenda-junio',
            'campaign': 'Cultura 2026',
            'category': 'Cultura',
            'location_name': 'Casa de la Cultura',
            'locality': 'Minas',
            'placement_type': 'folleto',
        },
    ]

    added = 0
    for lnk in sample_links:
        if not Link.query.filter_by(slug=lnk['slug']).first():
            link = Link(**lnk)
            db.session.add(link)
            added += 1

    db.session.commit()
    click.echo(f'[+] {added} demo links added.')


# ─── seed-local-dummy-auth ─────────────────────────────────────────────────────

@click.command('seed-local-dummy-auth')
@with_appcontext
def seed_local_dummy_auth():
    """Create or update a local testing super admin user for dummy auth."""
    from flask import current_app
    from .models import User
    from .utils.email_validation import normalize_and_validate_email

    if not current_app.config.get('ENABLE_LOCAL_DUMMY_AUTH'):
        click.echo('[!] ENABLE_LOCAL_DUMMY_AUTH is not true. Aborting.')
        return

    raw_email = current_app.config.get('LOCAL_DUMMY_EMAIL', 'admin@qr4all.dev')
    password = current_app.config.get('LOCAL_DUMMY_PASSWORD', 'Admin1234!')

    try:
        email = normalize_and_validate_email(raw_email)
    except ValueError:
        click.echo(f'[!] LOCAL_DUMMY_EMAIL "{raw_email}" is not a valid email. Use a real-format email like admin@qr4all.dev')
        return

    # Warn if old .local email exists in DB
    old_local = User.query.filter_by(email='admin@qr4all.local').first()
    if old_local:
        click.echo('[!] Found old user "admin@qr4all.local" in database.')
        click.echo('    This email is no longer valid for login. Consider deactivating it manually.')

    user = User.query.filter_by(email=email).first()
    if user:
        user.name = 'QR4All Local Admin'
        user.role = 'super_admin'
        user.is_active = True
        user.set_password(password)
        db.session.commit()
        click.echo(f'[+] Updated existing user "{email}" as local dummy admin.')
    else:
        user = User(
            name='QR4All Local Admin',
            email=email,
            role='super_admin',
            is_active=True,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f'[+] Created local dummy admin: {email} (id={user.id}).')

    click.echo(f'    Dummy 2FA code: {current_app.config.get("LOCAL_DUMMY_2FA_CODE", "123456")}')


# ─── seed-analytics-dummy ─────────────────────────────────────────────────────

@click.command('seed-analytics-dummy')
@click.option('--file', 'file_path', default=None, help='Path to the JSON seed file.')
@click.option('--dry-run', is_flag=True, default=False, help='Validate and show what would be inserted without committing.')
@click.option('--reset-dummy', 'reset_dummy', is_flag=True, default=False, help='Delete existing dummy data before re-seeding.')
@click.option('--allow-production', 'allow_production', is_flag=True, default=False, help='Allow running in production environment.')
@with_appcontext
def seed_analytics_dummy(file_path, dry_run, reset_dummy, allow_production):
    """Load analytics dummy data from JSON seed file."""
    import json
    import os
    from datetime import datetime, timezone
    from flask import current_app
    from sqlalchemy import func as sa_func
    from .models import User, Link, QrCode, ClickEvent

    # ── Production guard ──────────────────────────────────────────────────
    env = current_app.config.get('ENV_NAME', 'production')
    if env not in ('development', 'testing') and not allow_production:
        click.echo('[!] Refusing to seed analytics dummy data outside development/testing without --allow-production.')
        return

    # ── Locate JSON file ──────────────────────────────────────────────────
    if not file_path:
        file_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'seeds', 'qr4all_analytics_dummy_seed.json',
        )

    if not os.path.isfile(file_path):
        click.echo(f'[!] Seed file not found: {file_path}')
        return

    # ── Load and validate JSON ────────────────────────────────────────────
    click.echo(f'[*] Loading seed file: {file_path}')
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    required_keys = ('seed_name', 'seed_version', 'links', 'qr_codes', 'click_events', 'expected_analytics')
    for key in required_keys:
        if key not in data:
            click.echo(f'[!] Missing required key in JSON: {key}')
            return

    click.echo(f'    Seed name: {data["seed_name"]}')
    click.echo(f'    Seed version: {data["seed_version"]}')
    click.echo(f'    Links: {len(data["links"])}')
    click.echo(f'    QR codes: {len(data["qr_codes"])}')
    click.echo(f'    Click events: {len(data["click_events"])}')

    # ── Dry-run: just report ──────────────────────────────────────────────
    if dry_run:
        click.echo('\n[DRY RUN] Would insert:')
        click.echo(f'  Links: {len(data["links"])}')
        click.echo(f'  QR codes: {len(data["qr_codes"])}')
        click.echo(f'  Click events: {len(data["click_events"])}')
        click.echo('\n[DRY RUN] No changes committed.')
        return

    # ── Helpers ───────────────────────────────────────────────────────────
    def parse_iso_dt(value):
        if not value:
            return None
        return datetime.fromisoformat(value.replace('Z', '+00:00'))

    def ensure_user(email):
        """Find user by email, or fall back to first admin, or create a seed admin."""
        user = User.query.filter_by(email=email).first()
        if user:
            return user
        user = User.query.filter(User.role.in_(['admin', 'super_admin'])).first()
        if user:
            click.echo(f'  [~] User "{email}" not found, using existing admin: {user.email}')
            return user
        user = User(
            name='QR4All Seed Admin',
            email=email,
            role='admin',
            is_active=True,
        )
        user.set_password('SeedAdmin2026!')
        db.session.add(user)
        db.session.flush()
        click.echo(f'  [+] Created seed admin user: {email} (id={user.id})')
        return user

    # ── Reset dummy data if requested ─────────────────────────────────────
    seed_slugs = [lnk['slug'] for lnk in data['links']]
    if reset_dummy:
        click.echo('\n[*] Resetting existing dummy data...')
        seed_links = Link.query.filter(Link.slug.in_(seed_slugs)).all()
        if seed_links:
            seed_link_ids = [l.id for l in seed_links]
            deleted_events = ClickEvent.query.filter(ClickEvent.link_id.in_(seed_link_ids)).delete(synchronize_session=False)
            deleted_qr = QrCode.query.filter(QrCode.link_id.in_(seed_link_ids)).delete(synchronize_session=False)
            Link.query.filter(Link.id.in_(seed_link_ids)).delete(synchronize_session=False)
            db.session.flush()
            click.echo(f'  Deleted {deleted_events} click events, {deleted_qr} QR codes, {len(seed_links)} links.')

    # ── Phase 1: Insert/update Links ──────────────────────────────────────
    click.echo('\n[*] Phase 1: Links')
    links_created = 0
    links_updated = 0
    slug_to_link = {}
    email_to_user = {}

    for lnk_data in data['links']:
        slug = lnk_data['slug']
        existing = Link.query.filter_by(slug=slug).first()
        created_by_email = lnk_data.get('created_by_email')
        created_by_id = None

        if created_by_email:
            if created_by_email not in email_to_user:
                email_to_user[created_by_email] = ensure_user(created_by_email)
            created_by_id = email_to_user[created_by_email].id

        if existing:
            existing.title = lnk_data.get('title', existing.title)
            existing.description = lnk_data.get('description') or existing.description
            existing.original_url = lnk_data.get('original_url', existing.original_url)
            existing.campaign = lnk_data.get('campaign') or existing.campaign
            existing.category = lnk_data.get('category') or existing.category
            existing.location_name = lnk_data.get('location_name') or existing.location_name
            existing.locality = lnk_data.get('locality') or existing.locality
            existing.placement_type = lnk_data.get('placement_type') or existing.placement_type
            existing.latitude = lnk_data.get('latitude') if lnk_data.get('latitude') is not None else existing.latitude
            existing.longitude = lnk_data.get('longitude') if lnk_data.get('longitude') is not None else existing.longitude
            existing.is_active = lnk_data.get('is_active', existing.is_active)
            if lnk_data.get('expires_at'):
                existing.expires_at = parse_iso_dt(lnk_data['expires_at'])
            if created_by_id:
                existing.created_by_id = created_by_id
            db.session.flush()
            slug_to_link[slug] = existing
            links_updated += 1
            click.echo(f'  [~] Updated link: {slug}')
        else:
            link = Link(
                title=lnk_data['title'],
                description=lnk_data.get('description'),
                original_url=lnk_data['original_url'],
                slug=slug,
                campaign=lnk_data.get('campaign'),
                category=lnk_data.get('category'),
                location_name=lnk_data.get('location_name'),
                locality=lnk_data.get('locality'),
                placement_type=lnk_data.get('placement_type'),
                latitude=lnk_data.get('latitude'),
                longitude=lnk_data.get('longitude'),
                is_active=lnk_data.get('is_active', True),
                expires_at=parse_iso_dt(lnk_data.get('expires_at')),
                created_at=parse_iso_dt(lnk_data.get('created_at')) or datetime.now(timezone.utc),
                updated_at=parse_iso_dt(lnk_data.get('updated_at')) or datetime.now(timezone.utc),
                created_by_id=created_by_id,
            )
            db.session.add(link)
            db.session.flush()
            slug_to_link[slug] = link
            links_created += 1
            click.echo(f'  [+] Created link: {slug}')

    db.session.flush()

    # ── Phase 2: Insert/update QR codes ───────────────────────────────────
    click.echo('\n[*] Phase 2: QR Codes')
    qr_created = 0
    qr_updated = 0
    ext_id_to_qr = {}
    link_qr_map = {}  # link_id -> {name -> QrCode}

    for qr_data in data['qr_codes']:
        link_slug = qr_data['link_slug']
        ext_id = qr_data['external_id']

        if link_slug not in slug_to_link:
            click.echo(f'  [!] QR code {ext_id}: link slug "{link_slug}" not found, skipping.')
            continue

        link = slug_to_link[link_slug]
        link_id = link.id
        qr_name = qr_data.get('name')

        existing = None
        if link_id in link_qr_map and qr_name in link_qr_map[link_id]:
            existing = link_qr_map[link_id][qr_name]
        else:
            existing = QrCode.query.filter_by(
                link_id=link_id,
                name=qr_name,
                format=qr_data.get('format', 'png'),
                generated_url=qr_data.get('generated_url', ''),
            ).first()

        if existing:
            existing.size = qr_data.get('size', existing.size)
            existing.fill_color = qr_data.get('fill_color', existing.fill_color)
            existing.back_color = qr_data.get('back_color', existing.back_color)
            existing.error_correction = qr_data.get('error_correction', existing.error_correction)
            existing.has_logo = qr_data.get('has_logo', existing.has_logo)
            existing.logo_path = qr_data.get('logo_path') or existing.logo_path
            existing.logo_original_name = qr_data.get('logo_original_name') or existing.logo_original_name
            existing.logo_mime_type = qr_data.get('logo_mime_type') or existing.logo_mime_type
            db.session.flush()
            ext_id_to_qr[ext_id] = existing
            link_qr_map.setdefault(link_id, {})[qr_name] = existing
            qr_updated += 1
            click.echo(f'  [~] Updated QR: {ext_id} (link={link_slug})')
        else:
            qr = QrCode(
                link_id=link_id,
                name=qr_name,
                format=qr_data.get('format', 'png'),
                size=qr_data.get('size', 512),
                fill_color=qr_data.get('fill_color', '#000000'),
                back_color=qr_data.get('back_color', '#ffffff'),
                error_correction=qr_data.get('error_correction', 'M'),
                generated_url=qr_data.get('generated_url', ''),
                has_logo=qr_data.get('has_logo', False),
                logo_path=qr_data.get('logo_path'),
                logo_original_name=qr_data.get('logo_original_name'),
                logo_mime_type=qr_data.get('logo_mime_type'),
                created_at=parse_iso_dt(qr_data.get('created_at')) or datetime.now(timezone.utc),
            )
            db.session.add(qr)
            db.session.flush()
            ext_id_to_qr[ext_id] = qr
            link_qr_map.setdefault(link_id, {})[qr_name] = qr
            qr_created += 1
            click.echo(f'  [+] Created QR: {ext_id} (link={link_slug})')

    db.session.flush()

    # ── Phase 3: Insert click events (idempotent by fingerprint) ──────────
    click.echo('\n[*] Phase 3: Click Events')
    events_inserted = 0
    events_skipped = 0
    warnings = 0
    timestamps = []

    # Pre-fetch existing fingerprints for seed link IDs only
    seed_link_ids = [slug_to_link[s].id for s in seed_slugs if s in slug_to_link]
    existing_fingerprints = set()
    if seed_link_ids:
        existing_rows = db.session.query(
            ClickEvent.link_id,
            ClickEvent.timestamp,
            ClickEvent.ip_hash,
            ClickEvent.user_agent_raw,
            ClickEvent.path,
            ClickEvent.status_code,
        ).filter(ClickEvent.link_id.in_(seed_link_ids)).all()
        for row in existing_rows:
            # Normalize timestamp to ISO string for stable comparison
            ts = row.timestamp
            if ts and hasattr(ts, 'strftime'):
                ts_str = ts.strftime('%Y-%m-%dT%H:%M:%S')
            else:
                ts_str = str(ts) if ts else ''
            key = (
                row.link_id,
                ts_str,
                row.ip_hash or '',
                (row.user_agent_raw or '')[:100],
                row.path or '',
                row.status_code,
            )
            existing_fingerprints.add(key)

    click.echo(f'  Found {len(existing_fingerprints)} existing fingerprints for seed links.')

    for evt_data in data['click_events']:
        link_slug = evt_data['link_slug']
        qr_ext_id = evt_data.get('qr_external_id')

        if link_slug not in slug_to_link:
            click.echo(f'  [!] Event {evt_data["external_id"]}: link slug "{link_slug}" not found, skipping.')
            warnings += 1
            continue

        link_id = slug_to_link[link_slug].id
        qr_code_id = None
        if qr_ext_id and qr_ext_id in ext_id_to_qr:
            qr_code_id = ext_id_to_qr[qr_ext_id].id
        elif qr_ext_id:
            click.echo(f'  [!] Event {evt_data["external_id"]}: QR "{qr_ext_id}" not resolved, qr_code_id=None.')
            warnings += 1

        timestamp = parse_iso_dt(evt_data.get('timestamp'))

        # Fingerprint for idempotency
        ts_norm = timestamp.strftime('%Y-%m-%dT%H:%M:%S') if timestamp else ''
        fp_key = (
            link_id,
            ts_norm,
            evt_data.get('ip_hash', ''),
            (evt_data.get('user_agent_raw', ''))[:100],
            evt_data.get('path', ''),
            evt_data.get('status_code'),
        )
        if fp_key in existing_fingerprints:
            events_skipped += 1
            continue

        event = ClickEvent(
            link_id=link_id,
            qr_code_id=qr_code_id,
            timestamp=timestamp,
            ip_hash=evt_data.get('ip_hash'),
            ip_anonymized=evt_data.get('ip_anonymized'),
            user_agent_raw=evt_data.get('user_agent_raw'),
            browser=evt_data.get('browser'),
            browser_version=evt_data.get('browser_version'),
            os=evt_data.get('os'),
            os_version=evt_data.get('os_version'),
            device_type=evt_data.get('device_type'),
            device_family=evt_data.get('device_family'),
            referrer=evt_data.get('referrer'),
            accept_language=evt_data.get('accept_language'),
            primary_language=evt_data.get('primary_language'),
            method=evt_data.get('method', 'GET'),
            path=evt_data.get('path'),
            status_code=evt_data.get('status_code'),
            is_bot=evt_data.get('is_bot', False),
        )
        db.session.add(event)
        existing_fingerprints.add(fp_key)
        events_inserted += 1
        if timestamp:
            timestamps.append(timestamp)

        # Flush every 200 events to avoid memory buildup
        if events_inserted % 200 == 0:
            db.session.flush()
            click.echo(f'  ... {events_inserted} events processed')

    db.session.flush()

    # ── Phase 4: Recalculate link.click_count and last_accessed_at ────────
    click.echo('\n[*] Phase 4: Recalculating link analytics...')
    link_click_counts = {}

    for slug, link in slug_to_link.items():
        count = db.session.query(sa_func.count(ClickEvent.id)).filter(
            ClickEvent.link_id == link.id,
        ).scalar() or 0
        last_ts = db.session.query(sa_func.max(ClickEvent.timestamp)).filter(
            ClickEvent.link_id == link.id,
        ).scalar()
        link.click_count = count
        if last_ts:
            link.last_accessed_at = last_ts
        link_click_counts[slug] = count

    db.session.flush()

    # ── Commit ────────────────────────────────────────────────────────────
    db.session.commit()

    # ── Summary ───────────────────────────────────────────────────────────
    ts_sorted = sorted(timestamps) if timestamps else []
    date_range = ''
    if ts_sorted:
        date_range = f'{ts_sorted[0].strftime("%Y-%m-%d")} -> {ts_sorted[-1].strftime("%Y-%m-%d")}'

    click.echo('\n' + '=' * 60)
    click.echo('QR4All analytics dummy seed completed.')
    click.echo('=' * 60)
    click.echo(f'Links created: {links_created}')
    click.echo(f'Links updated: {links_updated}')
    click.echo(f'QR codes created: {qr_created}')
    click.echo(f'QR codes updated: {qr_updated}')
    click.echo(f'Click events inserted: {events_inserted}')
    click.echo(f'Click events skipped: {events_skipped}')
    click.echo(f'Warnings: {warnings}')
    if date_range:
        click.echo(f'Date range: {date_range}')

    click.echo('\nTop links by click count:')
    sorted_links = sorted(link_click_counts.items(), key=lambda x: x[1], reverse=True)
    for slug, count in sorted_links:
        link = slug_to_link.get(slug)
        title = link.title if link else slug
        click.echo(f'  - {title}: {count}')

    click.echo(f'\nSeed name: {data["seed_name"]}')
    click.echo(f'Seed version: {data["seed_version"]}')
    click.echo('\nVerification endpoints:')
    click.echo('  GET /api/analytics/overview')
    click.echo('  GET /api/analytics/timeseries')
    click.echo('  GET /api/analytics/top-links')
    click.echo('  GET /api/analytics/devices')
    click.echo('  GET /api/analytics/browsers')
    click.echo('  GET /api/analytics/os')
    click.echo('  GET /api/analytics/referrers')
    click.echo('  GET /api/analytics/languages')
    click.echo('  GET /api/analytics/hourly')
    click.echo('  GET /api/analytics/recent')
    click.echo('  GET /api/links/<id>/analytics')


# ─── repair-alembic ───────────────────────────────────────────────────────────

@click.command('repair-alembic')
@with_appcontext
def repair_alembic():
    """Stamp alembic_version to head (use when migrations are out of sync)."""
    from flask_migrate import stamp
    stamp()
    click.echo('[+] Alembic stamped to head.')


# ─── backfill-media-assets-from-qr-logos ──────────────────────────────────────

@click.command('backfill-media-assets-from-qr-logos')
@click.option('--dry-run', is_flag=True, default=False,
              help='Report what would be created without inserting.')
@with_appcontext
def backfill_media_assets_from_qr_logos(dry_run):
    """One-time backfill: register existing QR logos as reusable media assets.

    Scans qr_codes for rows with logo_object_key but no logo_asset_id,
    creates a media_assets row for each (if one does not already exist for
    that object_key), and links the qr_codes row to it.
    Skips rows whose object already exists in media_assets.
    Safe to re-run.
    """
    from .extensions import db
    from .models import QrCode, MediaAsset
    from .services.storage import storage_service

    qrs = QrCode.query.filter(
        QrCode.logo_object_key.isnot(None),
        QrCode.logo_object_key != '',
    ).all()

    created_assets = 0
    linked_existing = 0
    skipped_missing_object = 0
    already_backfilled = 0

    for qr in qrs:
        if qr.logo_asset_id:
            already_backfilled += 1
            continue

        existing = MediaAsset.query.filter_by(
            object_key=qr.logo_object_key,
        ).first()
        if existing is not None:
            qr.logo_asset_id = existing.id
            if not dry_run:
                db.session.add(qr)
            linked_existing += 1
            continue

        if not storage_service.available:
            skipped_missing_object += 1
            click.echo(
                f'[!] Storage unavailable — cannot backfill '
                f'qr_code id={qr.id} key={qr.logo_object_key}'
            )
            continue

        try:
            data = storage_service.get_object_bytes(qr.logo_object_key)
        except Exception as exc:
            skipped_missing_object += 1
            click.echo(
                f'[!] Cannot read MinIO object {qr.logo_object_key} '
                f'for qr_code id={qr.id}: {exc}'
            )
            continue

        if data is None:
            skipped_missing_object += 1
            click.echo(
                f'[!] MinIO object not found for qr_code id={qr.id} '
                f'key={qr.logo_object_key} — skipped'
            )
            continue

        import hashlib as _hashlib
        from datetime import datetime, timezone
        from PIL import Image
        import io as _io

        checksum = _hashlib.sha256(data).hexdigest()

        # Deduplicate against existing assets by checksum as well
        by_hash = MediaAsset.query.filter_by(
            checksum_sha256=checksum, category='qr_logo', is_active=True,
        ).first()
        if by_hash is not None:
            qr.logo_asset_id = by_hash.id
            if not dry_run:
                db.session.add(qr)
            linked_existing += 1
            continue

        # Determine content type and dimensions
        content_type = qr.logo_mime_type or 'image/png'
        try:
            img = Image.open(_io.BytesIO(data))
            width, height = img.size
        except Exception:
            width, height = None, None

        asset = MediaAsset(
            name=(qr.logo_original_name or qr.logo_object_key.split('/')[-1])[:200],
            description='Backfilled from existing QR logo',
            object_key=qr.logo_object_key,
            original_filename=qr.logo_original_name,
            content_type=content_type,
            size_bytes=len(data),
            width=width,
            height=height,
            checksum_sha256=checksum,
            category='qr_logo',
            is_active=True,
            created_by_id=qr.link.created_by_id if qr.link else None,
            created_at=datetime.now(timezone.utc),
        )
        if not dry_run:
            db.session.add(asset)
            db.session.flush()  # populate asset.id
            qr.logo_asset_id = asset.id
            db.session.add(qr)
        created_assets += 1

    if not dry_run:
        db.session.commit()

    click.echo(
        f'[+] Backfill complete: '
        f'created_assets={created_assets} '
        f'linked_existing={linked_existing} '
        f'skipped_missing_object={skipped_missing_object} '
        f'already_backfilled={already_backfilled}'
    )
    if dry_run:
        click.echo('[i] Dry run — no changes committed.')
