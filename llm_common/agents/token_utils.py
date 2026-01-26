import base64
import hashlib
import hmac
import json
import time
from typing import Any


def sign_token(payload: dict[str, Any], secret: str) -> str:
    """Create a signed token (v1 format).

    Format: v1.<payload_b64url>.<sig_b64url>
    """
    payload_json = json.dumps(payload, separators=(",", ":"))
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode().rstrip("=")

    header = "v1"
    msg = f"{header}.{payload_b64}"

    sig = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).decode().rstrip("=")

    return f"{msg}.{sig_b64}"


def verify_token(token: str, secret: str) -> dict[str, Any] | None:
    """Verify a signed token and return payload if valid."""
    try:
        parts = token.split(".")
        if len(parts) != 3 or parts[0] != "v1":
            return None

        header, payload_b64, sig_b64 = parts
        msg = f"{header}.{payload_b64}"

        # Verify signature
        expected_sig = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).digest()
        expected_sig_b64 = base64.urlsafe_b64encode(expected_sig).decode().rstrip("=")

        if not hmac.compare_digest(sig_b64, expected_sig_b64):
            return None

        # Decode payload
        # Add back padding if needed
        padding = "=" * (4 - len(payload_b64) % 4)
        payload_json = base64.urlsafe_b64decode(payload_b64 + padding).decode()
        payload = json.loads(payload_json)

        # Check expiration
        exp = payload.get("exp")
        if exp and time.time() > exp:
            return None

        return payload
    except Exception:
        return None
