import logging
import os
import time
from dataclasses import dataclass
from dataclasses import replace
from typing import TYPE_CHECKING, Any, Literal

logger = logging.getLogger(__name__)

AuthMode = Literal["none", "cookie_bypass", "ui_login", "storage_state"]
LaneMode = Literal["deterministic", "exploratory"]
UI_LOGIN_BOOTSTRAP = "ui_login"

if TYPE_CHECKING:
    from llm_common.agents.runtime.playwright_adapter import PlaywrightAdapter
else:
    PlaywrightAdapter = Any


@dataclass
class AuthConfig:
    mode: AuthMode = "none"
    bootstrap: str | None = None
    auth_redirect_check_path: str | None = None
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

    def with_runtime_overrides(self, runtime: "StoryRuntimeConfig") -> "AuthConfig":
        """Create an AuthConfig view for a story/runtime override."""
        return replace(
            self,
            mode=runtime.auth_mode,
            bootstrap=runtime.bootstrap,
            auth_redirect_check_path=runtime.auth_redirect_check_path,
        )


@dataclass(frozen=True)
class StoryRuntimeConfig:
    """Generic shared-runner config resolved from story metadata plus runner defaults."""

    auth_mode: AuthMode
    bootstrap: str | None = None
    auth_redirect_check_path: str | None = None

    @property
    def uses_ui_login(self) -> bool:
        return self.auth_mode == "ui_login" or self.bootstrap == UI_LOGIN_BOOTSTRAP


def resolve_story_runtime_config(
    metadata: dict[str, Any] | None,
    default_auth_config: AuthConfig,
) -> StoryRuntimeConfig:
    """Resolve generic auth/bootstrap inputs for one story without product semantics."""
    metadata = metadata or {}

    auth_mode = metadata.get("auth_mode") or default_auth_config.mode
    if auth_mode not in {"none", "cookie_bypass", "ui_login", "storage_state"}:
        raise ValueError(f"Unsupported auth_mode: {auth_mode}")

    bootstrap = metadata.get("bootstrap", default_auth_config.bootstrap)

    # Legacy compatibility: map older story metadata onto the generic bootstrap surface.
    if metadata.get("requires_real_clerk") and bootstrap is None:
        logger.warning(
            "Story metadata 'requires_real_clerk' is deprecated; use bootstrap='ui_login' instead."
        )
        bootstrap = UI_LOGIN_BOOTSTRAP

    if auth_mode == "ui_login" and bootstrap is None:
        bootstrap = UI_LOGIN_BOOTSTRAP

    redirect_check_path = (
        metadata.get("auth_redirect_check_path") or default_auth_config.auth_redirect_check_path
    )

    return StoryRuntimeConfig(
        auth_mode=auth_mode,
        bootstrap=bootstrap,
        auth_redirect_check_path=redirect_check_path,
    )


class AuthManager:
    """Manages authentication states and persona isolation for UISmoke."""

    def __init__(self, config: AuthConfig):
        self.config = config

    async def _click_clerk_continue(self, page: Any) -> None:
        """Click Clerk's primary Continue CTA without matching social providers."""
        try:
            await page.get_by_role("button", name="Continue", exact=True).click(timeout=5000)
            return
        except Exception:
            pass

        selectors = [
            'button:text-is("Continue")',
            '[role="button"]:text-is("Continue")',
        ]
        for selector in selectors:
            try:
                await page.click(selector, timeout=5000)
                return
            except Exception:
                continue
        raise RuntimeError("Unable to find exact Clerk Continue button")

    def _is_not_fillable_password_error(self, error: Exception) -> bool:
        """Best-effort classification for password field not-ready errors."""
        message = str(error).lower()
        not_fillable_markers = (
            "not visible",
            "not enabled",
            "not editable",
            "no node found",
            "strict mode violation",
            "element is not attached",
            "element is detached",
            "timeout",
        )
        return any(marker in message for marker in not_fillable_markers)

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

                await page.fill("input[name='identifier']", email)
                try:
                    await page.fill("input[name='password']", password)
                    await self._click_clerk_continue(page)
                except Exception as password_fill_error:
                    if not self._is_not_fillable_password_error(password_fill_error):
                        raise
                    await self._click_clerk_continue(page)
                    await page.fill("input[name='password']", password)
                    await self._click_clerk_continue(page)

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
