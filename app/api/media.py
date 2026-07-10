from flask import request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from . import api_bp, get_current_api_user, invalid_session_response
from ..models import MediaAsset
from ..services import media_service


def _bad(msg, code=400):
    return {"error": msg}, code


def _ok(data, code=200):
    return {"data": data}, code


def _require_admin(claims) -> bool:
    return claims.get('role') in ('admin', 'super_admin')


def _require_full_token():
    claims = get_jwt()
    if claims.get('type') == '2fa_pending':
        return _bad('Autenticación incompleta. Verifique su código 2FA.', 403)
    return None


@api_bp.route('/media/assets', methods=['GET'], strict_slashes=False)
@jwt_required()
def list_assets():
    err = _require_full_token()
    if err:
        return err

    category = request.args.get('category') or None
    assets = media_service.list_assets(category=category)
    return _ok([a.to_dict(include_preview_url=True) for a in assets])


@api_bp.route('/media/assets/<int:asset_id>', methods=['GET'], strict_slashes=False)
@jwt_required()
def get_asset(asset_id):
    err = _require_full_token()
    if err:
        return err
    asset = media_service.get_asset(asset_id)
    if not asset or not asset.is_active:
        return _bad('Imagen no encontrada.', 404)
    return _ok(asset.to_dict(include_preview_url=True))


@api_bp.route('/media/assets', methods=['POST'], strict_slashes=False)
@jwt_required()
def upload_asset():
    err = _require_full_token()
    if err:
        return err

    user = get_current_api_user()
    if user is None:
        return invalid_session_response()

    if not _require_admin(get_jwt()):
        return _bad('Solo administradores pueden subir imágenes a la biblioteca.', 403)

    if not request.content_type or 'multipart/form-data' not in request.content_type:
        return _bad('Se requiere multipart/form-data con el archivo.', 400)

    file = request.files.get('file')
    if not file:
        return _bad('Falta el campo "file".', 400)

    from ..services.storage import storage_service
    if not storage_service.available:
        return {
            'error': 'storage_unavailable',
            'message': 'El almacenamiento de imágenes no está disponible.',
        }, 503

    name = (request.form.get('name') or '').strip() or None
    category = (request.form.get('category') or 'qr_logo').strip()

    try:
        asset = media_service.upload_asset(
            file_storage=file,
            name=name,
            category=category,
            created_by_id=user.id,
        )
    except ValueError as exc:
        return _bad(str(exc))
    except Exception:
        current_app.logger.exception('Error uploading media asset')
        return {
            'error': 'asset_upload_failed',
            'message': 'No se pudo guardar la imagen. Intentá nuevamente.',
        }, 500

    return _ok(asset.to_dict(include_preview_url=True), 201)


@api_bp.route('/media/assets/<int:asset_id>', methods=['DELETE'], strict_slashes=False)
@jwt_required()
def delete_asset(asset_id):
    err = _require_full_token()
    if err:
        return err

    if not _require_admin(get_jwt()):
        return _bad('Solo administradores pueden eliminar imágenes de la biblioteca.', 403)

    if not media_service.soft_delete_asset(asset_id):
        return _bad('Imagen no encontrada.', 404)
    return _ok({'message': 'Imagen desactivada.'})