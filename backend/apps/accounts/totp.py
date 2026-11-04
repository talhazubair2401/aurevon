"""Authenticator-app codes (TOTP, RFC 6238: HMAC-SHA1, 6 digits, 30-second steps) and secret encryption."""

import base64
import hashlib
import hmac
import io
import secrets
import struct
import time
from urllib.parse import quote, urlencode

import segno
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.conf import settings

STEP_SECONDS = 30
DIGITS = 6
ISSUER = "AureVon"


def new_secret() -> str:
    """A 160-bit shared secret, base32 as authenticator apps expect."""
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def code_at(secret: str, step: int) -> str:
    key = base64.b32decode(secret + "=" * (-len(secret) % 8))
    digest = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10**DIGITS).zfill(DIGITS)


def current_step(now: float | None = None) -> int:
    return int((time.time() if now is None else now) // STEP_SECONDS)


def matching_step(secret: str, code: str, after_step: int, now: float | None = None) -> int | None:
    """The time step the code belongs to (one step of clock drift allowed either way), or None.
    Steps at or before `after_step` are refused, so a code can't be replayed."""
    code = code.strip().replace(" ", "")
    if len(code) != DIGITS or not code.isdigit():
        return None
    step = current_step(now)
    for candidate in (step - 1, step, step + 1):
        if candidate > after_step and hmac.compare_digest(code_at(secret, candidate), code):
            return candidate
    return None


def provisioning_uri(secret: str, email: str) -> str:
    label = quote(f"{ISSUER}:{email}")
    query = urlencode(
        {"secret": secret, "issuer": ISSUER, "algorithm": "SHA1", "digits": DIGITS, "period": STEP_SECONDS}
    )
    return f"otpauth://totp/{label}?{query}"


def qr_svg(uri: str) -> str:
    """The provisioning URI as an inline SVG QR code, so no third-party service ever sees the secret."""
    buffer = io.BytesIO()
    segno.make(uri, error="m").save(buffer, kind="svg", scale=5, border=2, xmldecl=False, svgns=True)
    return buffer.getvalue().decode()


def _fernet() -> Fernet:
    configured: str = getattr(settings, "MFA_ENCRYPTION_KEY", "")
    if configured:
        return Fernet(configured.encode())
    # Local and test only: production requires MFA_ENCRYPTION_KEY (config/settings/production.py).
    derived = HKDF(algorithm=hashes.SHA256(), length=32, salt=b"aurevon-mfa", info=b"totp-secret").derive(
        settings.SECRET_KEY.encode()
    )
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt_secret(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()
