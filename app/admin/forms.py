from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, EmailField, SelectField
from wtforms.validators import DataRequired, Length, Optional, ValidationError

from ..utils.email_validation import normalize_and_validate_email


def _validate_email_field(form, field):
    """WTForms validator that uses the same email validation as the API."""
    if not field.data:
        raise ValidationError('Ingresá un correo electrónico válido.')
    try:
        # Normalize in-place so downstream code gets a clean email
        field.data = normalize_and_validate_email(field.data)
    except ValueError:
        raise ValidationError('Ingresá un correo electrónico válido.')


class AdminLoginForm(FlaskForm):
    email = EmailField("Correo Electrónico", validators=[DataRequired(), _validate_email_field])
    password = PasswordField("Contraseña", validators=[DataRequired()])
    captcha = StringField("Verificación", validators=[DataRequired()])


class TwoFAForm(FlaskForm):
    code = StringField(
        "Código de Seguridad",
        validators=[DataRequired(), Length(min=6, max=6)],
    )


class CreateUserForm(FlaskForm):
    name = StringField("Nombre", validators=[DataRequired(), Length(max=100)])
    email = EmailField("Correo", validators=[DataRequired(), _validate_email_field, Length(max=150)])
    password = PasswordField("Contraseña", validators=[DataRequired(), Length(min=8, max=128)])
    role = SelectField(
        "Rol",
        choices=[("admin", "Administrador"), ("super_admin", "Super Admin")],
        validators=[DataRequired()],
    )


class EditUserForm(FlaskForm):
    name = StringField("Nombre", validators=[DataRequired(), Length(max=100)])
    role = SelectField(
        "Rol",
        choices=[("admin", "Administrador"), ("super_admin", "Super Admin")],
        validators=[DataRequired()],
    )
    new_password = PasswordField(
        "Nueva contraseña",
        validators=[
            Optional(),
            Length(min=8, max=128, message="La contraseña debe tener entre 8 y 128 caracteres."),
        ],
    )
    confirm_password = PasswordField(
        "Confirmar nueva contraseña",
        validators=[Optional()],
    )

    def validate(self, extra_validators=None):
        # Run WTForms field-level validators first.
        if not super().validate(extra_validators):
            return False

        new_password = (self.new_password.data or "").strip()
        confirm_password = (self.confirm_password.data or "").strip()

        # Both empty → password is not being changed: nothing to validate.
        if not new_password and not confirm_password:
            return True

        # Only one filled → ask the user to complete both.
        if not new_password or not confirm_password:
            msg = "Completá ambos campos para cambiar la contraseña."
            self.new_password.errors.append(msg)
            self.confirm_password.errors.append(msg)
            return False

        # Both filled but they don't match.
        if new_password != confirm_password:
            self.confirm_password.errors.append("Las contraseñas no coinciden.")
            return False

        # Length checks are also enforced by the field-level Length() validator,
        # but we re-check defensively in case validators were stripped.
        if len(new_password) < 8:
            self.new_password.errors.append(
                "La contraseña debe tener al menos 8 caracteres."
            )
            return False
        if len(new_password) > 128:
            self.new_password.errors.append(
                "La contraseña no puede superar los 128 caracteres."
            )
            return False

        return True
