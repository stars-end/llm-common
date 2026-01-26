import logging
from dataclasses import dataclass
from typing import Literal

from llm_common.agents.runtime.playwright_adapter import PlaywrightAdapter

logger = logging.getLogger(__name__)

AuthMode = Literal["none", "cookie_bypass", "ui_login", "storage_state"]

@dataclass
class AuthConfig:
    mode: AuthMode = "none"
    # For cookie_bypass
    cookie_name: str | None = None
    cookie_value: str | None = None
    cookie_domain: str | None = None
    # For ui_login
    email: str | None = None
    password: str | None = None
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
            if not self.config.cookie_name or not self.config.cookie_value:
                logger.error("cookie_name and cookie_value required for cookie_bypass mode")
                return False

            # Set cookie via Playwright context
            cookie = {
                "name": self.config.cookie_name,
                "value": self.config.cookie_value,
                "domain": self.config.cookie_domain or "",
                "path": "/",
            }
            # Note: PlaywrightAdapter currently only exposes Page, but we need Context for cookies.
            # We'll assume the caller of create_playwright_context handles storage_state,
            # but for cookie_bypass we might need to inject via page.context.add_cookies
            await adapter.page.context.add_cookies([cookie])
            logger.info(f"Set bypass cookie: {self.config.cookie_name}")
            return True

        if self.config.mode == "ui_login":
            if not self.config.email or not self.config.password:
                logger.error("email and password required for ui_login mode")
                return False

            logger.info(f"Performing UI login for {self.config.email} at {self.config.login_path}...")
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

                await page.fill("input[name='identifier']", self.config.email)
                await page.click("button:has-text('Continue')")
                await page.fill("input[name='password']", self.config.password)
                await page.click("button:has-text('Continue')")

                # Wait for redirect away from sign-in
                await page.wait_for_url(lambda u: "/sign-in" not in u, timeout=30000)
                logger.info("UI Login successful")
                return True
            except Exception as e:
                logger.error(f"UI Login failed: {e}")
                return False

        return True

    async def verify_auth(self, adapter: PlaywrightAdapter, dashboard_path: str = "/dashboard") -> bool:
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
