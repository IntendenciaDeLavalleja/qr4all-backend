from flask import request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from . import api_bp, get_current_api_user, invalid_session_response
from ..extensions import db
from ..models import Link
from ..services import link_service


def _bad(msg, code=400):
    return {"error": msg}, code


def _ok(data, code=200):
    return {"data": data}, code


def _require_full_token():
    claims = get_jwt()
    if claims.get("type") == "2fa_pending":
        return _bad("Autenticación incompleta. Verifique su código 2FA.", 403)
    return None


def _base_url():
    return current_app.config.get('PUBLIC_API_BASE_URL', 'http://localhost:5000')


@api_bp.route('/links', methods=['POST'], strict_slashes=False)
@jwt_required()
def create_link():
    err = _require_full_token()
    if err:
        return err

    user = get_current_api_user()
    if user is None:
        return invalid_session_response()

    body = request.get_json(silent=True) or {}

    try:
        link = link_service.create_link(body, user.id)
    except ValueError as e:
        return _bad(str(e))
    except IntegrityError:
        db.session.rollback()
        current_app.logger.warning(
            "IntegrityError during link creation — possible stale session."
        )
        return invalid_session_response()

    return _ok(link.to_detail_dict(_base_url()), 201)


@api_bp.route('/links', methods=['GET'], strict_slashes=False)
@jwt_required()
def list_links():
    err = _require_full_token()
    if err:
        return err

    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(100, max(1, request.args.get('per_page', 20, type=int)))
    search = (request.args.get('search') or '').strip()
    campaign = (request.args.get('campaign') or '').strip()
    category = (request.args.get('category') or '').strip()
    locality = (request.args.get('locality') or '').strip()
    is_active = request.args.get('is_active')
    sort = (request.args.get('sort') or 'created_at').strip()

    query = Link.query

    if search:
        like = f'%{search}%'
        query = query.filter(
            or_(
                Link.title.ilike(like),
                Link.slug.ilike(like),
                Link.original_url.ilike(like),
                Link.description.ilike(like),
            )
        )

    if campaign:
        query = query.filter(Link.campaign.ilike(f'%{campaign}%'))
    if category:
        query = query.filter(Link.category.ilike(f'%{category}%'))
    if locality:
        query = query.filter(Link.locality.ilike(f'%{locality}%'))

    if is_active is not None:
        if is_active.lower() in ('true', '1'):
            query = query.filter_by(is_active=True)
        elif is_active.lower() in ('false', '0'):
            query = query.filter_by(is_active=False)

    sort_map = {
        'created_at': Link.created_at.desc(),
        'click_count': Link.click_count.desc(),
        'title': Link.title.asc(),
        'last_accessed_at': Link.last_accessed_at.desc(),
    }
    query = query.order_by(sort_map.get(sort, Link.created_at.desc()))

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    base = _base_url()

    return _ok({
        'items': [l.to_detail_dict(base) for l in pagination.items],
        'pagination': {
            'page': pagination.page,
            'per_page': pagination.per_page,
            'total': pagination.total,
            'pages': pagination.pages,
        }
    })


@api_bp.route('/links/<int:link_id>', methods=['GET'], strict_slashes=False)
@jwt_required()
def get_link(link_id):
    err = _require_full_token()
    if err:
        return err

    link = Link.query.get(link_id)
    if not link:
        return _bad("Enlace no encontrado.", 404)

    base = _base_url()
    data = link.to_detail_dict(base)

    qr_codes = [q.to_dict() for q in link.qr_codes.all()]
    data['qr_codes'] = qr_codes

    return _ok(data)


@api_bp.route('/links/<int:link_id>', methods=['PUT'], strict_slashes=False)
@jwt_required()
def update_link(link_id):
    err = _require_full_token()
    if err:
        return err

    link = Link.query.get(link_id)
    if not link:
        return _bad("Enlace no encontrado.", 404)

    body = request.get_json(silent=True) or {}
    try:
        link = link_service.update_link(link, body)
    except ValueError as e:
        return _bad(str(e))

    return _ok(link.to_detail_dict(_base_url()))


@api_bp.route('/links/<int:link_id>', methods=['DELETE'], strict_slashes=False)
@jwt_required()
def delete_link(link_id):
    err = _require_full_token()
    if err:
        return err

    link = Link.query.get(link_id)
    if not link:
        return _bad("Enlace no encontrado.", 404)

    link_service.soft_delete_link(link)
    return _ok({"message": "Enlace deshabilitado correctamente."})
