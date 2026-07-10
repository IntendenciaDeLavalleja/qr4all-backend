from flask import request
from flask_jwt_extended import jwt_required, get_jwt

from . import api_bp
from ..services import analytics_service


def _ok(data, code=200):
    return {"data": data}, code


def _bad(msg, code=400):
    return {"error": msg}, code


def _require_full_token():
    claims = get_jwt()
    if claims.get("type") == "2fa_pending":
        return _bad("Autenticación incompleta.", 403)
    return None


@api_bp.route('/analytics/overview', methods=['GET'], strict_slashes=False)
@jwt_required()
def overview():
    err = _require_full_token()
    if err:
        return err
    return _ok(analytics_service.get_overview())


@api_bp.route('/analytics/timeseries', methods=['GET'], strict_slashes=False)
@jwt_required()
def timeseries():
    err = _require_full_token()
    if err:
        return err
    range_str = request.args.get('range', '30d')
    return _ok(analytics_service.get_timeseries(range_str))


@api_bp.route('/analytics/top-links', methods=['GET'], strict_slashes=False)
@jwt_required()
def top_links():
    err = _require_full_token()
    if err:
        return err
    range_str = request.args.get('range', '30d')
    return _ok(analytics_service.get_top_links(range_str))


@api_bp.route('/analytics/devices', methods=['GET'], strict_slashes=False)
@jwt_required()
def devices():
    err = _require_full_token()
    if err:
        return err
    range_str = request.args.get('range', '30d')
    return _ok(analytics_service.get_device_breakdown(range_str))


@api_bp.route('/analytics/referrers', methods=['GET'], strict_slashes=False)
@jwt_required()
def referrers():
    err = _require_full_token()
    if err:
        return err
    range_str = request.args.get('range', '30d')
    return _ok(analytics_service.get_referrers(range_str))


@api_bp.route('/analytics/languages', methods=['GET'], strict_slashes=False)
@jwt_required()
def languages():
    err = _require_full_token()
    if err:
        return err
    range_str = request.args.get('range', '30d')
    return _ok(analytics_service.get_languages(range_str))


@api_bp.route('/analytics/browsers', methods=['GET'], strict_slashes=False)
@jwt_required()
def browsers():
    err = _require_full_token()
    if err:
        return err
    range_str = request.args.get('range', '30d')
    return _ok(analytics_service.get_browser_breakdown(range_str))


@api_bp.route('/analytics/os', methods=['GET'], strict_slashes=False)
@jwt_required()
def os_breakdown():
    err = _require_full_token()
    if err:
        return err
    range_str = request.args.get('range', '30d')
    return _ok(analytics_service.get_os_breakdown(range_str))


@api_bp.route('/analytics/hourly', methods=['GET'], strict_slashes=False)
@jwt_required()
def hourly():
    err = _require_full_token()
    if err:
        return err
    range_str = request.args.get('range', '30d')
    return _ok(analytics_service.get_hourly_breakdown(range_str))


@api_bp.route('/analytics/recent', methods=['GET'], strict_slashes=False)
@jwt_required()
def recent_events():
    err = _require_full_token()
    if err:
        return err
    limit = min(100, max(1, request.args.get('limit', 20, type=int)))
    return _ok(analytics_service.get_recent_events(limit))


@api_bp.route('/links/<int:link_id>/analytics', methods=['GET'], strict_slashes=False)
@jwt_required()
def link_analytics(link_id):
    err = _require_full_token()
    if err:
        return err
    range_str = request.args.get('range', '30d')
    data = analytics_service.get_link_analytics(link_id, range_str)
    if not data:
        return _bad("Enlace no encontrado.", 404)
    return _ok(data)
