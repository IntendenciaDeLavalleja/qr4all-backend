"""
QR4All Lavalleja – Flask HTML Admin Panel
Routes at /admin/...

Auth flow:
  GET/POST /admin/login    – email + password + math captcha → sends 2FA code
  GET/POST /admin/2fa      – verify 6-digit code → Flask-Login session
  GET      /admin/logout   – clear session

Protected routes (login_required + admin/super_admin role):
  GET      /admin/              → /admin/dashboard
  GET      /admin/dashboard     – KPI cards + recent activity
  GET/POST /admin/users         – list + create user
  GET/POST /admin/users/<id>/edit   – edit user
  POST     /admin/users/<id>/toggle  – toggle is_active
  GET      /admin/logs          – activity log (super_admin only)
  GET      /admin/logs/export.csv – CSV export (super_admin only)
"""
import csv
import io
import random
from datetime import datetime, timezone
from functools import wraps

from flask import (
    render_template,
    redirect,
    url_for,
    request,
    flash,
    session,
    current_app,
    abort,
    Response,
)
from flask_login import login_user, logout_user, login_required, current_user

from . import admin_bp
from .forms import (
    AdminLoginForm,
    TwoFAForm,
    CreateUserForm,
    EditUserForm,
)
from ..extensions import db
from ..models import User, TwoFactorCode, ActivityLog, Link
from ..services.email_service import send_2fa_email


def _require_admin_role(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


def _require_super_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_super_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


def _log_admin(action, details=None):
    log = ActivityLog(
        user_id=current_user.id if current_user.is_authenticated else None,
        username=current_user.name if current_user.is_authenticated else "SISTEMA",
        action=f"admin:{action}",
        details=details,
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string,
    )
    db.session.add(log)


def _regenerate_captcha() -> None:
    """Generate a new math captcha and store the answer (int) in session."""
    a, b = random.randint(1, 20), random.randint(1, 20)
    session["captcha_answer"] = a + b
    session["captcha_question"] = f"{a} + {b} = ?"


def _is_local_dummy_auth_allowed() -> bool:
    """True only when local dummy auth is enabled AND not in production.

    Guards the dummy 2FA bypass so it can never run in production.
    """
    if not current_app.config.get("ENABLE_LOCAL_DUMMY_AUTH"):
        return False
    env_name = (current_app.config.get("ENV_NAME") or "").strip().lower()
    if env_name == "production":
        return False
    # FLASK_DEBUG is True in local development/testing; treat that as safe.
    return bool(current_app.config.get("DEBUG") or current_app.debug)


def _user_deletable(
    target: "User",
    actor: "User",
    active_super_admin_count: int,
    active_admin_count: int,
) -> bool:
    """Return True if `actor` is allowed to delete `target` right now.

    Mirrors the safety rules enforced in delete_user(); used by the
    /admin/users view to decide whether to render the Eliminar button.
    """
    if target.id == actor.id:
        return False
    if target.is_super_admin and not actor.is_super_admin:
        return False
    if target.is_super_admin and active_super_admin_count <= 1:
        return False
    if target.is_admin and target.is_active and active_admin_count <= 1:
        return False
    return True


# ─── login ────────────────────────────────────────────────────────────────────

@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated and current_user.is_admin:
        return redirect(url_for("admin.dashboard"))

    if request.method == "GET" or "captcha_answer" not in session:
        _regenerate_captcha()

    form = AdminLoginForm()
    if form.validate_on_submit():
        # ── Captcha: compare as int (form sends string, session stores int) ──
        captcha_expected = session.get("captcha_answer")
        try:
            captcha_submitted = int((form.captcha.data or "").strip())
        except (TypeError, ValueError):
            captcha_submitted = None

        if captcha_expected is None or captcha_submitted != captcha_expected:
            current_app.logger.info("Admin login captcha failed")
            flash("Verificación de seguridad incorrecta.", "error")
            _regenerate_captcha()
            return render_template(
                "login.html", form=form,
                captcha_question=session["captcha_question"],
            )

        # Captcha passed: clear it so it cannot be reused on a later POST.
        session.pop("captcha_answer", None)
        session.pop("captcha_question", None)

        user = User.query.filter_by(
            email=form.email.data.strip().lower(), is_active=True
        ).first()

        if not user or not user.check_password(form.password.data):
            flash("Credenciales incorrectas.", "error")
            _regenerate_captcha()
            return render_template(
                "login.html", form=form,
                captcha_question=session["captcha_question"],
            )

        if not user.is_admin:
            flash("No tienes permisos de administrador.", "error")
            _regenerate_captcha()
            return render_template(
                "login.html", form=form,
                captcha_question=session["captcha_question"],
            )

        TwoFactorCode.query.filter_by(user_id=user.id).filter(
            TwoFactorCode.consumed_at.is_(None)
        ).delete(synchronize_session=False)
        code_entry = TwoFactorCode.generate(user)
        db.session.commit()

        # Dummy 2FA users receive the fixed code via the configured value;
        # real users get a random code by email. We still try to send the
        # email so the real flow is exercised, but the dummy bypass in
        # /admin/2fa will accept LOCAL_DUMMY_2FA_CODE without SMTP.
        dummy_email = current_app.config.get("LOCAL_DUMMY_EMAIL")
        skip_email = (
            _is_local_dummy_auth_allowed()
            and user.email == dummy_email
        )
        if not skip_email:
            try:
                send_2fa_email(
                    user.email, user.name, code_entry.code,
                    current_app._get_current_object(),
                )
            except Exception as exc:
                current_app.logger.error(
                    "Admin 2FA email error for %s: %s", user.email, exc
                )
        else:
            current_app.logger.info(
                "Admin 2FA email skipped for local dummy user"
            )

        session["admin_pending_user_id"] = user.id
        return redirect(url_for("admin.verify_2fa"))

    return render_template(
        "login.html",
        form=form,
        captcha_question=session.get("captcha_question", "? + ? = ?"),
    )


@admin_bp.route("/2fa", methods=["GET", "POST"])
def verify_2fa():
    pending_id = session.get("admin_pending_user_id")
    if not pending_id:
        return redirect(url_for("admin.login"))

    form = TwoFAForm()
    if form.validate_on_submit():
        user = User.query.get(pending_id)
        submitted_code = form.code.data.strip()

        # ── Dummy 2FA bypass (local/dev/testing only) ───────────────────────
        # Mirrors the frontend /api/auth/verify-2fa dummy branch so the admin
        # panel can complete login locally without a working SMTP server.
        # Strictly gated: never active in production.
        dummy_accepted = False
        if (
            user
            and user.is_active
            and user.is_admin
            and _is_local_dummy_auth_allowed()
            and user.email == current_app.config.get("LOCAL_DUMMY_EMAIL")
            and submitted_code
            == current_app.config.get("LOCAL_DUMMY_2FA_CODE")
        ):
            dummy_accepted = True
            current_app.logger.info(
                "Admin 2FA: local dummy bypass used for user id=%s", user.id
            )

        if not dummy_accepted:
            code_entry = (
                TwoFactorCode.query
                .filter_by(user_id=pending_id)
                .filter(TwoFactorCode.consumed_at.is_(None))
                .order_by(TwoFactorCode.id.desc())
                .first()
            )
            if not code_entry or not code_entry.is_valid(submitted_code):
                flash("Código inválido o expirado.", "error")
                return render_template("verify_2fa.html", form=form)
            code_entry.used = True

        user.last_login = datetime.now(timezone.utc)

        login_user(user, remember=False)
        session.pop("admin_pending_user_id", None)

        _log_admin("login_success")
        db.session.commit()

        return redirect(url_for("admin.dashboard"))

    return render_template("verify_2fa.html", form=form)


@admin_bp.route("/logout")
@login_required
def logout():
    _log_admin("logout")
    db.session.commit()
    logout_user()
    flash("Sesión cerrada.", "success")
    return redirect(url_for("admin.login"))


# ─── dashboard ────────────────────────────────────────────────────────────────

@admin_bp.route("/")
@admin_bp.route("/dashboard")
@login_required
@_require_admin_role
def dashboard():
    total_users = User.query.filter_by(is_active=True).count()
    total_links = Link.query.count()
    active_links = Link.query.filter_by(is_active=True).count()
    total_clicks = db.session.query(db.func.sum(Link.click_count)).scalar() or 0

    recent_logs = (
        ActivityLog.query
        .order_by(ActivityLog.timestamp.desc())
        .limit(15)
        .all()
    )

    return render_template(
        "dashboard.html",
        total_users=total_users,
        total_links=total_links,
        active_links=active_links,
        total_clicks=total_clicks,
        recent_logs=recent_logs,
    )


# ─── users ────────────────────────────────────────────────────────────────────

@admin_bp.route("/users", methods=["GET", "POST"])
@login_required
@_require_admin_role
def users():
    form = CreateUserForm()

    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data.strip().lower()).first():
            flash("Ya existe un usuario con ese correo.", "error")
        else:
            new_user = User(
                name=form.name.data.strip(),
                email=form.email.data.strip().lower(),
                role=form.role.data,
            )
            new_user.set_password(form.password.data)
            db.session.add(new_user)
            _log_admin("create_user", f"email={new_user.email} role={new_user.role}")
            db.session.commit()
            flash(f"Usuario «{new_user.name}» creado exitosamente.", "success")
            return redirect(url_for("admin.users"))

    page = request.args.get("page", 1, type=int)
    per_page = 20
    pagination = (
        User.query
        .order_by(User.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    # Pre-compute delete-eligibility flags for each user so the template
    # can hide the Eliminar button without exposing a destructive control
    # the backend would reject anyway. Backend still re-validates everything.
    active_super_admin_count = User.query.filter(
        User.role == "super_admin", User.is_active.is_(True)
    ).count()
    active_admin_count = User.query.filter(
        User.role.in_(("admin", "super_admin")),
        User.is_active.is_(True),
    ).count()
    users_with_delete = {
        u.id: _user_deletable(
            u, current_user, active_super_admin_count, active_admin_count
        )
        for u in pagination.items
    }

    return render_template(
        "users.html",
        users=pagination.items,
        users_with_delete=users_with_delete,
        pagination=pagination,
        form=form,
    )


@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@_require_admin_role
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    form = EditUserForm(obj=user)

    if form.validate_on_submit():
        if user.is_super_admin and not current_user.is_super_admin:
            flash("No puedes editar un super administrador.", "error")
            return redirect(url_for("admin.users"))

        user.name = form.name.data.strip()
        user.role = form.role.data

        # ── Optional password change ─────────────────────────────────────────
        # The form's validate() already enforces: both empty OK, both must be
        # filled together, must match, 8 <= len <= 128. Here we only need to
        # decide whether to actually hash + store a new password.
        new_password = (form.new_password.data or "").strip()
        password_changed = bool(new_password)
        if password_changed:
            user.set_password(new_password)
            _log_admin(
                "change_user_password",
                f"target_user_id={user.id} target_user_email={user.email}",
            )

        _log_admin(
            "edit_user",
            f"user_id={user.id} name={user.name} role={user.role} "
            f"password_changed={password_changed}",
        )
        db.session.commit()
        flash(f"Usuario «{user.name}» actualizado.", "success")
        return redirect(url_for("admin.users"))

    # GET request or validation failure: force password fields to render
    # empty even if the previous submit bounced back. This prevents any
    # user-typed value from being reflected in the markup.
    form.new_password.data = ""
    form.confirm_password.data = ""

    return render_template("edit_user.html", form=form, edit_user=user)


@admin_bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@login_required
@_require_admin_role
def toggle_user(user_id):
    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash("No puedes desactivar tu propia cuenta.", "error")
        return redirect(url_for("admin.users"))
    if user.is_super_admin and not current_user.is_super_admin:
        flash("No puedes desactivar a un super administrador.", "error")
        return redirect(url_for("admin.users"))

    user.is_active = not user.is_active
    action = "activate_user" if user.is_active else "deactivate_user"
    _log_admin(action, f"user_id={user.id} email={user.email}")
    db.session.commit()
    state = "activado" if user.is_active else "desactivado"
    flash(f"Usuario «{user.name}» {state}.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@_require_admin_role
def delete_user(user_id):
    """Permanently delete a user from the system.

    Safety rules (enforced server-side, regardless of UI):
      - Only POST (GET is a no-op via routing).
      - CSRF is enforced by Flask-WTF (csrf.protect on /admin/*).
      - Authenticated admin role required.
      - Cannot delete the currently authenticated user.
      - Cannot delete a super_admin unless the caller is a super_admin.
      - Cannot delete the last active super_admin.
      - Cannot leave the system with zero active admins.
      - Wraps db.session.delete + commit in try/except with rollback.
      - Records an ActivityLog entry before deletion.
    """
    user = User.query.get_or_404(user_id)

    # Rule 1: cannot self-delete.
    if user.id == current_user.id:
        flash(
            "No podés eliminar tu propia cuenta mientras estás autenticado.",
            "error",
        )
        return redirect(url_for("admin.users"))

    # Rule 2: non-super_admin cannot delete a super_admin.
    if user.is_super_admin and not current_user.is_super_admin:
        flash("No tenés permisos para eliminar un super administrador.", "error")
        return redirect(url_for("admin.users"))

    # Rule 3: cannot delete the last active super_admin.
    if user.is_super_admin:
        other_super_admins = User.query.filter(
            User.role == "super_admin",
            User.id != user.id,
            User.is_active.is_(True),
        ).count()
        if other_super_admins == 0:
            flash(
                "No podés eliminar el último super administrador activo.",
                "error",
            )
            return redirect(url_for("admin.users"))

    # Rule 4: cannot leave the system with zero active admins.
    # Count remaining active admins (admin or super_admin) after removal.
    if user.is_admin and user.is_active:
        remaining_admins = User.query.filter(
            User.id != user.id,
            User.is_active.is_(True),
            User.role.in_(("admin", "super_admin")),
        ).count()
        if remaining_admins == 0:
            flash(
                "No podés eliminar el último usuario administrador activo.",
                "error",
            )
            return redirect(url_for("admin.users"))

    # Capture identifying info before deletion for the audit log.
    deleted_id = user.id
    deleted_email = user.email
    deleted_name = user.name
    deleted_role = user.role

    # Audit log entry (must be flushed before the user is deleted so the
    # log row keeps a valid user_id reference; ActivityLog.user_id is
    # nullable + ondelete=SET NULL, so even flushing after would work,
    # but flushing first keeps the link for forensic value).
    _log_admin(
        "delete_user",
        (
            f"deleted_id={deleted_id} email={deleted_email} "
            f"role={deleted_role}"
        ),
    )

    try:
        # Explicitly NULL out the FK on related rows before deletion.
        # This honours the SET NULL contract on activity_logs.user_id
        # and links.created_by_id on databases (e.g. SQLite without the
        # FK pragma enabled) that do not enforce the schema-level
        # ON DELETE clause on their own. TwoFactorCode rows cascade-
        # delete via the relationship.
        ActivityLog.query.filter(
            ActivityLog.user_id == user.id
        ).update({ActivityLog.user_id: None}, synchronize_session=False)
        Link.query.filter(
            Link.created_by_id == user.id
        ).update({Link.created_by_id: None}, synchronize_session=False)

        db.session.delete(user)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(
            "Admin delete_user failed for id=%s: %s", deleted_id, exc
        )
        flash(
            "No se pudo eliminar el usuario. Revisá si tiene datos asociados.",
            "error",
        )
        return redirect(url_for("admin.users"))

    flash(f"Usuario «{deleted_name}» eliminado correctamente.", "success")
    return redirect(url_for("admin.users"))


# ─── logs ─────────────────────────────────────────────────────────────────────

@admin_bp.route("/logs")
@login_required
@_require_super_admin
def logs():
    page = request.args.get("page", 1, type=int)
    per_page = 50
    action_filter = request.args.get("action", "").strip()
    user_filter = request.args.get("user_id", "", type=str).strip()

    q = ActivityLog.query
    if action_filter:
        q = q.filter(ActivityLog.action.ilike(f"%{action_filter}%"))
    if user_filter.isdigit():
        q = q.filter(ActivityLog.user_id == int(user_filter))

    pagination = q.order_by(ActivityLog.timestamp.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    all_users = User.query.order_by(User.name).all()

    return render_template(
        "logs.html",
        logs=pagination.items,
        pagination=pagination,
        action_filter=action_filter,
        user_filter=user_filter,
        all_users=all_users,
    )


def _sanitize_csv_cell(value) -> str:
    """Return a safe string for a CSV cell.

    Prevents CSV-injection by prefixing cells that start with =, +, -, @ or
    tab with a single quote.  None is returned as an empty string.  Embedded
    line-breaks are replaced with spaces so they don't break CSV rows.
    """
    if value is None:
        return ""
    s = str(value).strip()
    # Replace newlines / carriage-returns to keep single-line cells
    s = s.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
    # Prefix formula-injection characters
    if s and s[0] in ("=", "+", "-", "@", "\t"):
        s = "'" + s
    return s


def _build_filtered_logs_query():
    """Return a SQLAlchemy query for activity logs, applying the same
    filters that the /admin/logs page uses.

    This avoids duplicating the query logic between the HTML view and
    the CSV export.
    """
    action_filter = request.args.get("action", "").strip()
    user_filter = request.args.get("user_id", "", type=str).strip()

    q = ActivityLog.query
    if action_filter:
        q = q.filter(ActivityLog.action.ilike(f"%{action_filter}%"))
    if user_filter.isdigit():
        q = q.filter(ActivityLog.user_id == int(user_filter))

    return q.order_by(ActivityLog.timestamp.desc())


@admin_bp.route("/logs/export.csv")
@login_required
@_require_super_admin
def logs_export_csv():
    """Download all matching activity logs as a CSV file.

    Accepts the same ``action`` and ``user_id`` query parameters as
    the HTML logs page so the export always reflects the current
    filter state.
    """
    query = _build_filtered_logs_query()

    # Generate filename with current server datetime
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"activity_logs_{now}.csv"

    # Build CSV in memory
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)

    # Header row
    writer.writerow([
        "id",
        "user_id",
        "user_name",
        "user_email",
        "action",
        "details",
        "ip_address",
        "created_at",
    ])

    # Data rows – iterate lazily so memory stays bounded
    for log in query.yield_per(500):
        # Resolve user info gracefully even when the user was deleted.
        user_name = ""
        user_email = ""
        if log.user:
            user_name = log.user.name or ""
            user_email = log.user.email or ""
        elif log.username:
            user_name = log.username

        writer.writerow([
            _sanitize_csv_cell(log.id),
            _sanitize_csv_cell(log.user_id),
            _sanitize_csv_cell(user_name),
            _sanitize_csv_cell(user_email),
            _sanitize_csv_cell(log.action),
            _sanitize_csv_cell(log.details),
            _sanitize_csv_cell(log.ip_address),
            _sanitize_csv_cell(log.timestamp.isoformat() if log.timestamp else ""),
        ])

    csv_bytes = buf.getvalue().encode("utf-8")

    return Response(
        csv_bytes,
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
