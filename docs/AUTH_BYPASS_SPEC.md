# QA Auth Bypass Specification (v1)

This document defines the standard for HMAC-signed authentication bypass used by QA agents (UISmoke) across the platform.

## 1. Goal

Provide a secure, deterministic, and fast way for automated agents to authenticate without interacting with third-party auth providers (e.g., Clerk) or relying on brittle UI flows.

## 2. Token Format (v1)

The bypass token is a period-separated string of three components:

`v1.<payload_b64url>.<signature_b64url>`

1.  **Header**: Fixed string `v1`.
2.  **Payload**: JSON object, Base64Url-encoded.
    ```json
    {
      "sub": "test_user",     // User identifier prefix (e.g., test_admin, test_user)
      "role": "admin",        // Role to assume
      "email": "test@...",    // Email address
      "exp": 1735689600       // Unix timestamp (UTC) for expiration
    }
    ```
3.  **Signature**: HMAC-SHA256 signature of `v1.<payload_b64url>` using the `TEST_AUTH_BYPASS_SECRET`, Base64Url-encoded.

## 3. Security Requirements

### 3.1 Environment Gating
**CRITICAL**: Authentication bypass MUST be disabled in production.
-   Backends MUST ONLY honor bypass tokens when `RAILWAY_ENVIRONMENT_NAME` is in `{dev, staging}` or when running locally.
-   Frontends MUST ONLY attempt bypass when `VITE_RAILWAY_ENVIRONMENT === 'dev'`.

### 3.2 Secret Management
-   The `TEST_AUTH_BYPASS_SECRET` MUST NOT be committed to git.
-   It MUST be managed via Railway environment variables.
-   It MUST NOT be substituted into LLM prompts or logs.

### 3.3 Expiration (TTL)
-   Tokens should have a short TTL (e.g., 30 minutes) to minimize risk if a token is leaked.

## 4. Implementation Reference

### 4.1 Backend (Python/FastAPI)
```python
from llm_common.agents.token_utils import verify_token

def auth_middleware(request):
    token = request.cookies.get("x-test-user")
    if token and is_bypass_env():
        payload = verify_token(token, os.environ["TEST_AUTH_BYPASS_SECRET"])
        if payload:
            return authenticated_user(payload)
```

### 4.2 Frontend (React/Vite)
```tsx
const shouldBypass = () => {
  return import.meta.env.VITE_RAILWAY_ENVIRONMENT === 'dev' &&
         document.cookie.includes('x-test-user=');
};
```

## 5. Audit Logging

Every successful bypass authentication MUST be logged with `sub` and `role` to ensure traceability.
