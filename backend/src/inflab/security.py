"""Credential encryption and redaction helpers."""

from __future__ import annotations

import base64
import hashlib

from pydantic import SecretStr


def _key_stream(master_key: str, length: int) -> bytes:
    blocks: list[bytes] = []
    counter = 0
    while sum(len(block) for block in blocks) < length:
        material = f"{master_key}:{counter}".encode()
        blocks.append(hashlib.sha256(material).digest())
        counter += 1
    return b"".join(blocks)[:length]


def encrypt_secret(secret: str, master_key: SecretStr) -> str:
    raw = secret.encode()
    stream = _key_stream(master_key.get_secret_value(), len(raw))
    encrypted = bytes(value ^ stream[index] for index, value in enumerate(raw))
    return base64.urlsafe_b64encode(encrypted).decode()


def decrypt_secret(encrypted: str, master_key: SecretStr) -> str:
    raw = base64.urlsafe_b64decode(encrypted.encode())
    stream = _key_stream(master_key.get_secret_value(), len(raw))
    decrypted = bytes(value ^ stream[index] for index, value in enumerate(raw))
    return decrypted.decode()


def mask_secret(secret: str | None) -> str:
    if not secret:
        return "not_configured"
    return "configured"


def redact_text(text: str) -> str:
    markers = ("password", "private_key", "token", "secret", "api_key")
    redacted_lines: list[str] = []
    for line in text.splitlines():
        lowered = line.lower()
        if any(marker in lowered for marker in markers):
            redacted_lines.append("[REDACTED]")
        else:
            redacted_lines.append(line)
    return "\n".join(redacted_lines)
