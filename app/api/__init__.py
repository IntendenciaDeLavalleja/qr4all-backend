from flask import Blueprint, current_app, jsonify
from flask_jwt_extended import get_jwt_identity

api_bp = Blueprint("api", __name__, url_prefix="/api")
auth_public_bp = Blueprint('auth_public', __name__)
redirect_bp = Blueprint('redirect', __name__)


def get_current_api_user():
    """Resolve the authenticated user from the JWT identity.

    Returns the User object if the JWT is valid AND the user still exists AND
    is active.  Returns None otherwise (stale JWT, deleted user, inactive
    account).

    Callers should return a 401 when this returns None so the frontend can
    clear its auth state and redirect to /login.
    """
    from ..extensions import db
    from ..models import User

    identity = get_jwt_identity()
    if identity is None:
        return None

    try:
        user_id = int(identity)
    except (TypeError, ValueError):
        return None

    user = db.session.get(User, user_id)
    if user is None:
        current_app.logger.warning(
            "JWT references missing user id=%s. Request rejected.", user_id
        )
        return None
    if hasattr(user, 'is_active') and not user.is_active:
        current_app.logger.warning(
            "JWT references inactive user id=%s. Request rejected.", user_id
        )
        return None

    return user


def invalid_session_response():
    """Standard 401 response for stale/invalid sessions."""
    return jsonify({
        "error": "invalid_session",
        "message": "La sesión ya no es válida. Iniciá sesión nuevamente.",
    }), 401


from . import (  # noqa: F401,E402
    auth,
    users,
    links,
    qr,
    analytics,
    redirect,
    media,
)
