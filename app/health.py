from flask import Blueprint, current_app, jsonify

health_bp = Blueprint('health', __name__)


@health_bp.route('/health', methods=['GET'])
def health():
    redis_available = bool(
        current_app.config.get('REDIS_AVAILABLE', False)
    )
    from .services.storage import storage_service
    storage_available = storage_service.available
    return jsonify({
        'status': 'ok',
        'redis': 'ok' if redis_available else 'unavailable',
        'storage': 'ok' if storage_available else 'unavailable',
    }), 200