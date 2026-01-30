import os
import time
import httpx
import pytest
from llm_common.agents.token_utils import sign_token

@pytest.mark.skipif(not os.getenv("TEST_AUTH_BYPASS_SECRET"), reason="No secret configured for integration test")
@pytest.mark.parametrize("app_url", [
    os.getenv("PRIME_BACKEND_URL", "http://localhost:8000"),
    os.getenv("AFFORDABOT_BACKEND_URL", "http://localhost:8001"),
])
def test_cross_app_auth_bypass_parity(app_url):
    """Verify that both apps respond correctly to the SAME v1 token."""
    secret = os.getenv("TEST_AUTH_BYPASS_SECRET")
    payload = {
        "sub": "qa-parity-test@example.com",
        "role": "admin",
        "exp": int(time.time()) + 300
    }
    token = sign_token(payload, secret)
    
    # Test via Cookie
    with httpx.Client(base_url=app_url) as client:
        # We hit /health or a similar lightweight protected endpoint if possible
        # For now, just checking if the server accepts the request without 401/403
        # if the middleware is correctly identifying the token.
        resp = client.get("/health", cookies={"x-test-user": token})
        
        # If the app is down, this will fail, which is fine for automation.
        # But here we just want to verify the logic parity if we can.
        assert resp.status_code == 200
        
    # Test via Header
    with httpx.Client(base_url=app_url) as client:
        resp = client.get("/health", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
