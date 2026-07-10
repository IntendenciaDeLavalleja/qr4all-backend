"""Email service for QR4All Lavalleja."""
from threading import Thread
from flask import current_app, render_template
from flask_mail import Message
from ..extensions import mail


def _send_async(app, msg: Message) -> None:
    with app.app_context():
        try:
            mail.send(msg)
        except Exception as exc:
            app.logger.error(f"Email send failed: {exc}")


def _send(subject: str, recipients: list[str], text: str, html: str) -> None:
    app = current_app._get_current_object()
    msg = Message(subject=subject, recipients=recipients)
    msg.body = text
    msg.html = html
    Thread(target=_send_async, args=(app, msg), daemon=True).start()


def _render(template_name: str, **kwargs) -> str:
    """Render a Jinja2 email template with the given context.

    This must be called inside a Flask application context (request or
    explicit ``app.app_context()``) so that ``render_template`` can
    locate the template files.
    """
    return render_template(f"emails/{template_name}", **kwargs)


#  ─── public helpers ────────────────────────────────────────────────────────


def send_2fa_email(to_email: str, user_name: str, code: str, app=None) -> None:
    """Send a 2-factor authentication code to the user."""
    _app = app or current_app._get_current_object()
    app_name = _app.config.get("APP_NAME", "QR4All Lavalleja")
    subject = f"[{app_name}] Código de verificación"

    # Plain-text fallback
    text = (
        f"Hola, {user_name}.\n\n"
        f"Usá este código para completar tu verificación de seguridad en {app_name}:\n\n"
        f"  {code}\n\n"
        f"Este código vence en 10 minutos.\n\n"
        f"Si no solicitaste este acceso, podés ignorar este correo.\n\n"
        f"{app_name} · Intendencia Departamental de Lavalleja\n"
        f"Este es un correo automático. Por favor, no respondas a este mensaje."
    )

    # Render HTML template
    html = _render(
        "two_factor_code.html",
        app_name=app_name,
        user_name=user_name,
        code=code,
        expiration_minutes=10,
        subject=subject,
    )

    msg = Message(subject=subject, recipients=[to_email])
    msg.body = text
    msg.html = html

    Thread(target=_send_async, args=(_app, msg), daemon=True).start()


def send_welcome_email(to_email: str, user_name: str, temp_password: str) -> None:
    """Send a welcome / credential email to a newly created user."""
    app = current_app._get_current_object()
    app_name = app.config.get("APP_NAME", "QR4All Lavalleja")
    frontend_url = app.config.get("FRONTEND_URL", "http://localhost:5173")
    subject = f"[{app_name}] Bienvenido/a — Credenciales de acceso"

    # Plain-text fallback
    text = (
        f"Hola, {user_name}.\n\n"
        f"Tu cuenta ha sido creada en {app_name}.\n"
        f"A continuación tenés tus credenciales de acceso iniciales:\n\n"
        f"  Email:              {to_email}\n"
        f"  Contraseña temporal: {temp_password}\n\n"
        f"Accedé en: {frontend_url}\n\n"
        f"Por seguridad, te recomendamos cambiar tu contraseña al ingresar por primera vez.\n\n"
        f"{app_name} · Intendencia Departamental de Lavalleja\n"
        f"Este es un correo automático. Por favor, no respondas a este mensaje."
    )

    # Render HTML template
    html = _render(
        "welcome.html",
        app_name=app_name,
        user_name=user_name,
        to_email=to_email,
        temp_password=temp_password,
        frontend_url=frontend_url,
        subject=subject,
    )

    _send(subject, [to_email], text, html)
