"""
Email validation utility for QR4All Lavalleja.

Provides a single function to normalize and validate email addresses
consistently across API login, admin panel forms, and CLI commands.

Uses email-validator with check_deliverability=False to avoid rejecting
syntactically valid emails due to missing MX records, while still
rejecting clearly invalid domains like .local, localhost, or bare domains.
"""

import re
from email_validator import validate_email, EmailNotValidError

# Domains or TLD patterns that must always be rejected
_BLOCKED_DOMAINS = {
    'localhost',
}

_BLOCKED_TLD_PATTERNS = (
    '.local',
    '.localhost',
    '.invalid',
    '.example',
    '.test',       # RFC 2606 reserved, but we explicitly allow .test for dev dummy emails
)

# We explicitly ALLOW .test for development dummy emails (e.g. admin@qr4all.dev)
# .dev is a real public TLD owned by Google, so it passes naturally.

_EMAIL_RE = re.compile(
    r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
)


def normalize_and_validate_email(email: str) -> str:
    """
    Normalize and validate an email address.

    Returns the normalized (lowercase, stripped) email on success.
    Raises ValueError with a user-facing Spanish message on failure.
    """
    if not isinstance(email, str):
        raise ValueError('Ingresá un correo electrónico válido.')

    cleaned = email.strip()
    if not cleaned:
        raise ValueError('Ingresá un correo electrónico válido.')

    # Quick structural check before calling email-validator
    if ' ' in cleaned:
        raise ValueError('Ingresá un correo electrónico válido.')

    parts = cleaned.rsplit('@', 1)
    if len(parts) != 2:
        raise ValueError('Ingresá un correo electrónico válido.')

    local, domain = parts
    domain_lower = domain.strip().lower()

    if not local or not domain_lower:
        raise ValueError('Ingresá un correo electrónico válido.')

    # Block localhost
    if domain_lower == 'localhost':
        raise ValueError('Ingresá un correo electrónico válido.')

    # Block .local and other reserved TLDs (but allow .dev, .test, .com, .uy, etc.)
    for blocked_tld in _BLOCKED_TLD_PATTERNS:
        if domain_lower == blocked_tld.lstrip('.') or domain_lower.endswith(blocked_tld):
            raise ValueError('Ingresá un correo electrónico válido.')

    # Block domains without a dot (no TLD)
    if '.' not in domain_lower:
        raise ValueError('Ingresá un correo electrónico válido.')

    # Use email-validator for full syntax validation (no deliverability check)
    try:
        result = validate_email(cleaned, check_deliverability=False)
        normalized = result.normalized
    except EmailNotValidError:
        raise ValueError('Ingresá un correo electrónico válido.')

    # Final safety: ensure the normalized email still looks right
    if not _EMAIL_RE.match(normalized):
        raise ValueError('Ingresá un correo electrónico válido.')

    return normalized


def is_valid_email_format(email: str) -> bool:
    """
    Check if an email has a valid format without raising exceptions.
    Returns True if valid, False otherwise.
    """
    try:
        normalize_and_validate_email(email)
        return True
    except ValueError:
        return False
