# Auth Bypass Specification (v1)

This spec defines a standardized method for bypassing authentication in QA and verification environments using HMAC-signed cookies or headers.

## Token Format
The token is a string in the format: `v1.<payload_b64url>.<signature_b64url>`

- `v1`: Version header.
- `payload_b64url`: Base64URL-encoded (no padding) JSON payload.
- `signature_b64url`: Base64URL-encoded (no padding) HMAC-SHA256 signature.

## Payload Schema
```json
{
  "sub": "string (email or user_id)",
  "role": "string (e.g., 'admin', 'user')",
  "iat": "int (Unix timestamp)",
  "exp": "int (Unix timestamp)"
}
```

## Signing Algorithm
`HMAC-SHA256(key=SECRET, message="v1.<payload_b64url>")`

## Transport
1.  **Cookie**: `x-test-user` (Standard for browser-driven smoke tests).
2.  **Header**: `Authorization: Bearer v1.<payload_b64url>.<signature_b64url>` (Standard for API-driven verification).

## Environment Constraints
- MUST only be enabled if `TEST_AUTH_BYPASS_SECRET` is set.
- MUST only be enabled in `development`, `dev`, `staging`, or `preview` environments (never `production`).

## Shared Test Vectors (Contract)
- **Secret**: `test-secret-12345`
- **Payload**: `{"sub": "qa@example.com", "role": "admin", "iat": 1738181400, "exp": 1738267800}`
- **Token**: `v1.eyJzdWIiOiJxYUBleGFtcGxlLmNvbSIsInJvbGUiOiJhZG1pbiIsImlhdCI6MTczODE4MTQwMCwiZXhwIjoxNzM4MjY3ODAwfQ.N_UueXzI_vD0l_R_M1j2_F2V_M1j2_F2V_M1j2_F2V_M1j2_F2V_M1j2_F2V_M1j2_F2V` (Example only, actual signature depends on implementation)
