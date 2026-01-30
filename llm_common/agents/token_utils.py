import base64
import hashlib
import hmac
import json
import time
from typing import Any


def sign_token(payload: dict[str, Any], secret: str) -> str:
    """Sign a payload using HMAC-SHA256 according to Auth Bypass v1 spec.
    
    Format: v1.<payload_b64url>.<sig_b64url>
    """
    if "iat" not in payload:
        payload["iat"] = int(time.time())
    
    payload_json = json.dumps(payload, separators=(",", ":"))
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode().rstrip("=")
    header = "v1"
    msg = f"{header}.{payload_b64}"
    
    sig = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).decode().rstrip("=")
    
    return f"{msg}.{sig_b64}"


def verify_token(token: str, secret: str) -> dict[str, Any]:
    """Verify a v1 token and return the payload.
    
    Raises ValueError for invalid format, signature, or expiration.
    """
    if not token.startswith("v1."):
        raise ValueError("Invalid token header (expected 'v1.')")

    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid token format (expected 3 parts)")

    header, payload_b64, sig_b64 = parts
    msg = f"{header}.{payload_b64}"

    # Verify signature
    expected_sig = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).digest()
    expected_sig_b64 = base64.urlsafe_b64encode(expected_sig).decode().rstrip("=")

    if not hmac.compare_digest(sig_b64, expected_sig_b64):
        raise ValueError("Invalid token signature")

    # Decode payload
    try:
        # Re-add padding if necessary
        missing_padding = len(payload_b64) % 4
        if missing_padding:
            payload_b64 += "=" * (4 - missing_padding)
        payload_json = base64.urlsafe_b64decode(payload_b64).decode()
        payload = json.loads(payload_json)
    except Exception as e:
        raise ValueError(f"Failed to decode payload: {e}")

    # Check expiration
    exp = payload.get("exp")
    if exp and time.time() > exp:
        raise ValueError("Token expired")

    return payload
