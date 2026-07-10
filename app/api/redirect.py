from datetime import datetime, timezone
from flask import redirect, current_app, jsonify, request
from . import redirect_bp
from ..models import Link
from ..services import analytics_service


@redirect_bp.route('/r/<slug>', methods=['GET'], strict_slashes=False)
def redirect_to_link(slug):
    link = Link.query.filter_by(slug=slug).first()

    if not link:
        return jsonify({"error": "Enlace no encontrado."}), 404

    if not link.is_active:
        return jsonify({"error": "Este enlace ha sido deshabilitado."}), 404

    if link.expires_at:
        now = datetime.now(timezone.utc)
        exp = link.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if now > exp:
            return jsonify({"error": "Este enlace ha expirado."}), 410

    ip_salt = current_app.config.get('IP_HASH_SALT', '')
    try:
        analytics_service.record_click(
            link=link,
            request_obj=request,
            ip_salt=ip_salt,
        )
    except Exception as exc:
        current_app.logger.error(f"Analytics recording failed for {slug}: {exc}")

    return redirect(link.original_url, code=302)
