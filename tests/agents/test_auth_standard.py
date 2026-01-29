import time
import pytest
from llm_common.agents.token_utils import sign_token, verify_token

def test_token_lifecycle():
    secret = "test-secret"
    payload = {"sub": "qa@example.com", "role": "admin", "exp": int(time.time()) + 60}
    
    token = sign_token(payload, secret)
    assert token.startswith("v1.")
    
    verified = verify_token(token, secret)
    assert verified["sub"] == "qa@example.com"
    assert verified["role"] == "admin"

def test_token_expiration():
    secret = "test-secret"
    payload = {"sub": "qa@example.com", "exp": int(time.time()) - 10}
    
    token = sign_token(payload, secret)
    with pytest.raises(ValueError, match="Token expired"):
        verify_token(token, secret)

def test_invalid_signature():
    secret = "test-secret"
    payload = {"sub": "qa@example.com"}
    token = sign_token(payload, secret)
    
    with pytest.raises(ValueError, match="Invalid token signature"):
        verify_token(token, "wrong-secret")

def test_invalid_format():
    with pytest.raises(ValueError, match="Invalid token header"):
        verify_token("v2.abcd.efgh", "secret")
        
@pytest.mark.parametrize("invalid_token,expected_match", [
    ("v1.payload", "Invalid token format"),
    ("v1.p.s.extra", "Invalid token format"),
])
def test_invalid_formats(invalid_token, expected_match):
    with pytest.raises(ValueError, match=expected_match):
        verify_token(invalid_token, "secret")

def test_payload_padding():
    # Test with payload that doesn't align to 4 bytes base64
    secret = "test-secret"
    payload = {"s": "a"} # Very short
    token = sign_token(payload, secret)
    verified = verify_token(token, secret)
    assert verified["s"] == "a"
