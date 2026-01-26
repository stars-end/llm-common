import logging
import os
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

logger = logging.getLogger(__name__)

AuthMode = Literal["none", "cookie_bypass", "ui_login", "storage_state"]

if TYPE_CHECKING:
    from llm_common.agents.runtime.playwright_adapter import PlaywrightAdapter
else:
    PlaywrightAdapter = Any


@dataclass
class AuthConfig:
    mode: AuthMode = "none"
    # For cookie_bypass
    cookie_name: str | None = None
    cookie_value: str | None = None
    cookie_domain: str | None = None  # "auto" or explicit
    cookie_signed: bool = False
    cookie_secret_env: str = "TEST_AUTH_BYPASS_SECRET"
    # For ui_login
    email: str | None = None
    password: str | None = None
    email_env: str = "TEST_USER_EMAIL"
    password_env: str = "TEST_USER_PASSWORD"
    login_path: str = "/sign-in"
    # For storage_state
    storage_state_path: str | None = None


class AuthManager:
    """Manages authentication states and persona isolation for UISmoke."""

    def __init__(self, config: AuthConfig):
        self.config = config

    async def apply_auth(self, adapter: PlaywrightAdapter) -> bool:
        """Apply authentication to a context via the adapter's page."""
        if self.config.mode == "none":
            return True

        if self.config.mode == "cookie_bypass":
            if not self.config.cookie_name:
                logger.error("cookie_name required for cookie_bypass mode")
                return False

            cookie_value = self.config.cookie_value
            if self.config.cookie_signed:
                secret = os.environ.get(self.config.cookie_secret_env)
                if not secret:
                    logger.error(f"Secret not found in env var: {self.config.cookie_secret_env}")
                    return False

                from llm_common.agents.token_utils import sign_token

                # Payload JSON: { "sub": "test_admin", "role": "admin", "email": "...", "exp": <unix_ts> }
                # We'll use the cookie_value as the sub/role prefix if it's 'admin' or 'user'
                sub = f"test_{cookie_value}" if cookie_value else "test_user"
                role = "admin" if cookie_value == "admin" else "user"

                payload = {
                    "sub": sub,
                    "role": role,
                    "email": f"{sub}@example.com",
                    "exp": int(time.time()) + 7200,  # 2 hours TTL
                }
                cookie_value = sign_token(payload, secret)
            else:
                if not cookie_value:
                    logger.error("cookie_value required for unsigned cookie_bypass")
                    return False

            # Set cookie via Playwright context
            domain = self.config.cookie_domain
            if domain == "auto":
                from urllib.parse import urlparse

                domain = urlparse(adapter.base_url).hostname

            cookie = {
                "name": self.config.cookie_name,
                "value": cookie_value,
                "domain": domain or "",
                "path": "/",
                "secure": adapter.base_url.startswith("https"),
                "sameSite": "Lax",
            }
            await adapter.page.context.add_cookies([cookie])
            logger.info(
                f"Set bypass cookie: {self.config.cookie_name} ({'signed' if self.config.cookie_signed else 'plain'}) (domain={domain})"
            )
            return True

        if self.config.mode == "ui_login":
            email = self.config.email or os.environ.get(self.config.email_env)
            password = self.config.password or os.environ.get(self.config.password_env)
            if not email or not password:
                logger.error(
                    f"UI login requires credentials: provide --email/--password or set env vars "
                    f"{self.config.email_env} and {self.config.password_env}"
                )
                return False

            logger.info(f"Performing UI login for {email} at {self.config.login_path}...")
            try:
                await adapter.navigate(self.config.login_path)
                # Clerk-specific or Generic fallback
                # This is a bit opinionated, downstream can override via stories if needed,
                # but we'll implement a fallback common flow.
                page = adapter.page

                # Check if already logged in
                if "/sign-in" not in page.url and "Sign in" not in await page.content():
                    logger.info("Already logged in (UI detection)")
                    return True

                # Try common Clerk pattern
                if await page.get_by_text("Sign in to continue").is_visible():
                    await page.click("text=Sign in to continue")

                await page.fill("input[name='identifier']", email)
                await page.click("button:has-text('Continue')")
                await page.fill("input[name='password']", password)
                await page.click("button:has-text('Continue')")

                # Wait for redirect away from sign-in
                await page.wait_for_url(lambda u: "/sign-in" not in u, timeout=30000)
                logger.info("UI Login successful")
                return True
            except Exception as e:
                logger.error(f"UI Login failed: {e}")
                return False

        return True

    async def verify_auth(
        self, adapter: PlaywrightAdapter, dashboard_path: str = "/dashboard"
    ) -> bool:
        """Verify that the current context has valid auth."""
        if self.config.mode == "none":
            return True

        logger.info(f"Verifying auth by navigating to {dashboard_path}...")
        try:
            await adapter.navigate(dashboard_path)
            # If redirected to sign-in, auth failed
            url = await adapter.get_current_url()
            if "/sign-in" in url:
                logger.warning(f"Auth verification failed: Redirected to {url}")
                return False
            return True
        except Exception as e:
            logger.error(f"Auth verification crashed: {e}")
            return False
