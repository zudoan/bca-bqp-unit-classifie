"""Password and session-token primitives using only Python's standard library."""
from __future__ import annotations

import base64
import hashlib
import secrets


PASSWORD_SCHEME = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 600_000
SALT_BYTES = 16
SESSION_TOKEN_BYTES = 48


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(SALT_BYTES)
    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )
    return f"{PASSWORD_SCHEME}${PASSWORD_ITERATIONS}${_encode(salt)}${_encode(derived_key)}"


def verify_password(password: str, encoded_password: str) -> bool:
    try:
        scheme, iterations_text, salt_text, expected_text = encoded_password.split("$", 3)
        iterations = int(iterations_text)
        if scheme != PASSWORD_SCHEME or not 100_000 <= iterations <= 1_000_000:
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            _decode(salt_text),
            iterations,
        )
        return secrets.compare_digest(actual, _decode(expected_text))
    except (TypeError, ValueError):
        return False


def create_session_token() -> str:
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

