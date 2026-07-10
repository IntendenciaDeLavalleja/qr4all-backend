from urllib.parse import urlparse
import ipaddress
import re

_BLOCKED_SCHEMES = frozenset({
    'javascript', 'data', 'file', 'ftp', 'mailto', 'tel',
    'vbscript', 'about', 'blob',
})

_PRIVATE_PREFIXES_V4 = [
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('127.0.0.0/8'),
    ipaddress.ip_network('0.0.0.0/8'),
]


def _is_private_ip(hostname: str) -> bool:
    try:
        addr = ipaddress.ip_address(hostname)
        if addr.is_loopback or addr.is_private or addr.is_link_local:
            return True
        for net in _PRIVATE_PREFIXES_V4:
            if addr in net:
                return True
        return False
    except ValueError:
        return False


def validate_url(url: str) -> tuple[bool, str | None]:
    if not url or not url.strip():
        return False, "URL es requerida."

    url = url.strip()

    try:
        parsed = urlparse(url)
    except Exception:
        return False, "URL inválida."

    if not parsed.scheme:
        return False, "URL debe incluir http:// o https://"

    scheme = parsed.scheme.lower()
    if scheme not in ('http', 'https'):
        return False, f"Esquema '{scheme}' no permitido. Solo http y https."

    if not parsed.netloc:
        return False, "URL debe tener un dominio válido."

    hostname = parsed.hostname or ''
    if not hostname:
        return False, "URL debe tener un hostname válido."

    blocked_patterns = [
        'localhost', '127.0.0.1', '0.0.0.0', '::1',
        '0:0:0:0', '[::1]',
    ]
    hostname_lower = hostname.lower()
    for bp in blocked_patterns:
        if bp in hostname_lower:
            return False, "URLs a localhost/redes privadas no están permitidas."

    if _is_private_ip(hostname):
        return False, "URLs a IPs privadas no están permitidas."

    return True, None


def normalize_url(url: str) -> str:
    url = url.strip()
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    return url
