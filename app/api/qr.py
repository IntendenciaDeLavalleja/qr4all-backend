from flask import request, current_app, send_file
from flask_jwt_extended import jwt_required, get_jwt
import io

from . import api_bp
from ..models import Link, QrCode
from ..services import qr_service


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


@api_bp.route('/links/<int:link_id>/qr', methods=['POST'], strict_slashes=False)
@jwt_required()
def create_qr(link_id):
    try:
        err = _require_full_token()
        if err:
            return err

        from . import get_current_api_user, invalid_session_response
        user = get_current_api_user()
        if user is None:
            return invalid_session_response()

        link = Link.query.get(link_id)
        if not link:
            return _bad("Enlace no encontrado.", 404)

        base = _base_url()
        short_url = link.short_url(base)

        is_multipart = request.content_type and 'multipart/form-data' in request.content_type
        logo_file = request.files.get('logo_file') if is_multipart else None

        # logo_asset_id can be sent as form field (multipart) or JSON body
        if is_multipart:
            logo_asset_id_raw = request.form.get('logo_asset_id')
            body = request.form
        else:
            body = request.get_json(silent=True) or {}
            logo_asset_id_raw = body.get('logo_asset_id')

        logo_asset_id = None
        if logo_asset_id_raw is not None and logo_asset_id_raw != '':
            try:
                logo_asset_id = int(logo_asset_id_raw)
            except (TypeError, ValueError):
                return {
                    "error": "invalid_logo_source",
                    "message": "logo_asset_id inválido.",
                }, 400

        if logo_file and logo_asset_id is not None:
            return {
                "error": "invalid_logo_source",
                "message": "Elegí subir una imagen nueva o seleccionar una existente, no ambas.",
            }, 400

        logo_asset = None
        if logo_asset_id is not None:
            from ..models import MediaAsset
            from ..services import media_service
            logo_asset = media_service.get_asset(logo_asset_id)
            if not logo_asset or not logo_asset.is_active:
                return {
                    "error": "logo_asset_not_found",
                    "message": "La imagen seleccionada no existe o ya no está disponible.",
                }, 404

        # If a new logo will be uploaded, require storage availability
        if logo_file or logo_asset is not None:
            from ..services.storage import storage_service
            if not storage_service.available:
                return {
                    "error": "storage_unavailable",
                    "message": "El almacenamiento de imágenes no está disponible.",
                }, 503

        qr = qr_service.create_qr_record(
            link_id=link.id,
            generated_url=short_url,
            name=body.get('name'),
            fmt=body.get('format', 'png'),
            size=int(body.get('size', 512)) if body.get('size') else 512,
            fill_color=body.get('fill_color', '#000000'),
            back_color=body.get('back_color', '#ffffff'),
            error_correction=body.get('error_correction', 'M'),
            logo_file=logo_file,
            logo_asset=logo_asset,
            created_by_id=user.id,
        )

        data = qr.to_dict(include_logo_url=True)
        data['download_url'] = f'/api/links/{link_id}/qr/{qr.id}/download'
        return _ok(data, 201)
    except ValueError as exc:
        return _bad(str(exc))
    except Exception:
        current_app.logger.exception("Error creating QR for link %s", link_id)
        return {
            "error": "qr_creation_failed",
            "message": "No se pudo generar el QR. Intentá nuevamente.",
        }, 500


@api_bp.route('/links/<int:link_id>/qr/<int:qr_id>/download', methods=['GET'], strict_slashes=False)
@jwt_required()
def download_qr(link_id, qr_id):
    try:
        err = _require_full_token()
        if err:
            return err

        qr = QrCode.query.filter_by(id=qr_id, link_id=link_id).first()
        if not qr:
            return _bad("QR no encontrado.", 404)

        image_bytes, mimetype = qr_service.generate_qr_image(
            url=qr.generated_url,
            fmt=qr.format,
            size=qr.size,
            fill_color=qr.fill_color,
            back_color=qr.back_color,
            error_correction=qr.error_correction,
            qr=qr,
        )

        ext = 'svg' if qr.format == 'svg' else 'png'
        filename = f"qr_{qr.link.slug}_{qr.id}.{ext}"

        return send_file(
            io.BytesIO(image_bytes),
            mimetype=mimetype,
            as_attachment=True,
            download_name=filename,
        )
    except Exception as exc:
        current_app.logger.exception("Error downloading QR %s for link %s", qr_id, link_id)
        return _bad(f"Error interno al descargar QR: {exc}", 500)


@api_bp.route('/links/<int:link_id>/qr/download', methods=['GET'], strict_slashes=False)
@jwt_required()
def download_default_qr(link_id):
    try:
        err = _require_full_token()
        if err:
            return err

        link = Link.query.get(link_id)
        if not link:
            return _bad("Enlace no encontrado.", 404)

        base = _base_url()
        short_url = link.short_url(base)

        fmt = request.args.get('format', 'png')
        size = int(request.args.get('size', 512))
        fill_color = request.args.get('fill_color', '#000000')
        back_color = request.args.get('back_color', '#ffffff')

        image_bytes, mimetype = qr_service.generate_qr_image(
            url=short_url,
            fmt=fmt,
            size=size,
            fill_color=fill_color,
            back_color=back_color,
        )

        ext = 'svg' if fmt == 'svg' else 'png'
        filename = f"qr_{link.slug}.{ext}"

        return send_file(
            io.BytesIO(image_bytes),
            mimetype=mimetype,
            as_attachment=True,
            download_name=filename,
        )
    except Exception as exc:
        current_app.logger.exception("Error downloading default QR for link %s", link_id)
        return _bad(f"Error interno al descargar QR: {exc}", 500)


@api_bp.route('/links/<int:link_id>/qr/preview', methods=['GET'], strict_slashes=False)
@jwt_required()
def preview_qr(link_id):
    try:
        err = _require_full_token()
        if err:
            return err

        link = Link.query.get(link_id)
        if not link:
            return _bad("Enlace no encontrado.", 404)

        base = _base_url()
        short_url = link.short_url(base)

        fmt = request.args.get('format', 'png')
        size = min(1024, max(64, int(request.args.get('size', 256))))

        # If a primary QR with logo exists, use it for preview so logo is visible
        primary_qr = QrCode.query.filter_by(link_id=link_id).order_by(QrCode.id.desc()).first()

        image_bytes, mimetype = qr_service.generate_qr_image(
            url=short_url,
            fmt=fmt,
            size=size,
            qr=primary_qr,
        )

        return send_file(
            io.BytesIO(image_bytes),
            mimetype=mimetype,
        )
    except Exception as exc:
        current_app.logger.exception("Error previewing QR for link %s", link_id)
        return _bad(f"Error interno al previsualizar QR: {exc}", 500)
