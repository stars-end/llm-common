import asyncio
import base64
import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from playwright.async_api import Browser, BrowserContext, Page
from playwright.async_api import TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)

# Default timeouts (can be overridden per context)
DEFAULT_NAV_TIMEOUT_MS = int(os.environ.get("NAV_TIMEOUT_MS", "30000"))
DEFAULT_ACTION_TIMEOUT_MS = int(os.environ.get("ACTION_TIMEOUT_MS", "30000"))

# Default blocked resource patterns (analytics, telemetry, etc. that cause networkidle flakes)
DEFAULT_BLOCKED_RESOURCES = [
    "google-analytics.com",
    "segment.io",
    "sentry.io",
    "hotjar.com",
    "intercom.io",
    "fullstory.com",
]


class PlaywrightAdapter:
    """Canonical Playwright implementation of BrowserAdapter.

    Features:
    - No networkidle (uses domcontentloaded + manual app-ready waits)
    - Robust retry logic for all interactions
    - Network blocking for telemetry/analytics
    - Forensics (console logs, network errors, traces)
    """

    def __init__(
        self,
        page: Page,
        base_url: str,
        nav_timeout_ms: int | None = None,
        action_timeout_ms: int | None = None,
    ):
        self.page = page
        self.base_url = base_url.rstrip("/")
        self.nav_timeout_ms = (
            nav_timeout_ms if nav_timeout_ms is not None else DEFAULT_NAV_TIMEOUT_MS
        )
        self.action_timeout_ms = (
            action_timeout_ms if action_timeout_ms is not None else DEFAULT_ACTION_TIMEOUT_MS
        )

        self._console_errors: list[str] = []
        self._network_errors: list[dict[str, Any]] = []
        self._setup_listeners()

    def _setup_listeners(self) -> None:
        """Monitor console and network for errors."""

        def on_console(msg):
            if msg.type in ("error", "warning"):
                self._console_errors.append(f"[{msg.type}] {msg.text}")

        def on_request_failed(request):
            failure = request.failure
            if failure:
                # Filter out blocked resources from error lists to reduce noise
                # Note: This still uses local BLOCKED_RESOURCES if it's been updated by create_playwright_context
                # But for simplicity in the listener, we just check against common patterns
                if any(p in request.url for p in DEFAULT_BLOCKED_RESOURCES):
                    return
                self._network_errors.append(
                    {
                        "url": request.url,
                        "method": request.method,
                        "message": failure,
                    }
                )

        self.page.on("console", on_console)
        self.page.on("requestfailed", on_request_failed)

    async def _retry_action(self, action_name: str, func: Callable, retries: int = 3) -> Any:
        """Execute an action with retry logic for detachment/timeouts."""
        last_error = None
        for i in range(retries):
            try:
                return await func()
            except PlaywrightTimeout:
                last_error = PlaywrightTimeout(f"{action_name} timed out after {retries} attempts")
                logger.warning(
                    f"{action_name} timed out (attempt {i+1}/{retries}). Retrying in {2**i}s..."
                )
                await asyncio.sleep(2**i)
            except Exception as e:
                # Retry on typical SPA-related Playwright errors
                if any(
                    msg in str(e).lower()
                    for msg in ["detached", "target closed", "context was destroyed"]
                ):
                    logger.warning(
                        f"Browser state error during {action_name} (attempt {i+1}). Retrying..."
                    )
                    await asyncio.sleep(1)
                    last_error = e
                else:
                    raise e

        raise last_error

    async def navigate(self, path: str) -> None:
        """Navigate to a relative path using domcontentloaded strategy."""
        url = urljoin(self.base_url, path)
        logger.info(f"Navigating to {url}")
        try:
            # Use domcontentloaded to avoid hanging on background analytics/segment traffic
            await self.page.goto(url, wait_until="domcontentloaded", timeout=self.nav_timeout_ms)

            # Application-specific "ready" signals can be added here or via wait_for_selector in story
            # For robustness, we wait for body to be visible
            try:
                await self.page.wait_for_selector(
                    "body", state="visible", timeout=min(5000, self.nav_timeout_ms)
                )
            except Exception:
                pass

            # Brief hydration pause
            await asyncio.sleep(2)
        except Exception as e:
            from llm_common.agents.exceptions import NavigationError

            raise NavigationError(f"Navigation to {url} failed: {e}")

    async def click(self, target: str) -> None:
        """Perform a robust click (supports selector and text)."""
        logger.info(f"Clicking: {target}")

        async def _do_click():
            # Try text-based matching if not a selector
            if not any(target.startswith(p) for p in ["[", "#", ".", "text="]):
                selector = f"text={target}"
            else:
                selector = target

            # force=True bypasses strict actionability checks if needed,
            # but we use it sparingly to ensure user-like behavior
            await self.page.click(selector, timeout=self.action_timeout_ms, force=True)

        try:
            await self._retry_action(f"click({target})", _do_click)
        except Exception as e:
            from llm_common.agents.exceptions import ElementNotFoundError

            raise ElementNotFoundError(f"Click failed for {target}: {e}")

    async def type_text(self, selector: str, text: str) -> None:
        """Type text into a field using keyboard simulation."""
        logger.info(f"Typing into {selector}")

        async def _do_type():
            # Wait for field to be ready
            locator = self.page.locator(selector)
            await locator.wait_for(state="visible", timeout=self.action_timeout_ms)

            # Click to focus
            await locator.click(timeout=self.action_timeout_ms, force=True)

            # Clear existing text (Select All + Backspace)
            await self.page.keyboard.press("Control+A")
            await self.page.keyboard.press("Meta+A")  # Mac support
            await self.page.keyboard.press("Backspace")

            # Type naturally
            await self.page.keyboard.type(text)
            await asyncio.sleep(0.5)

        try:
            await self._retry_action(f"type_text({selector})", _do_type)
        except Exception as e:
            from llm_common.agents.exceptions import ElementNotFoundError

            raise ElementNotFoundError(f"Type failed for {selector}: {e}")

    async def screenshot(self) -> str:
        """Capture a full-page screenshot as base64."""
        screenshot_bytes = await self.page.screenshot(type="png", full_page=True)
        return base64.b64encode(screenshot_bytes).decode("utf-8")

    async def get_console_errors(self) -> list[str]:
        """Return and clear captured console errors."""
        errors = self._console_errors[:]
        self._console_errors.clear()
        return errors

    async def get_network_errors(self) -> list[dict[str, Any]]:
        """Return and clear captured network errors."""
        errors = self._network_errors[:]
        self._network_errors.clear()
        return errors

    async def wait_for_selector(self, selector: str, timeout_ms: int = 10000) -> None:
        """Wait for an element to appear."""
        await self.page.wait_for_selector(selector, timeout=timeout_ms)

    async def get_current_url(self) -> str:
        return self.page.url

    async def get_content(self) -> str:
        return await self.page.content()

    async def get_text(self, selector: str) -> str:
        """Return inner text of an element."""
        return await self.page.inner_text(selector)

    async def close(self) -> None:
        await self.page.close()


async def create_playwright_context(
    base_url: str,
    headless: bool = True,
    storage_state: str | None = None,
    tracing: bool = False,
    block_domains: list[str] | None = None,
    no_default_blocklist: bool = False,
    nav_timeout_ms: int | None = None,
    action_timeout_ms: int | None = None,
) -> tuple[Browser, BrowserContext, PlaywrightAdapter]:
    """Factory to create a correctly configured Playwright context."""
    from playwright.async_api import async_playwright

    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=headless)

    context_options = {
        "viewport": {"width": 1280, "height": 800},
        "bypass_csp": True,
        "ignore_https_errors": True,
    }

    if storage_state and Path(storage_state).exists():
        context_options["storage_state"] = storage_state
        logger.info(f"Using storage state: {storage_state}")

    context = await browser.new_context(**context_options)

    # Network blocking: prevent analytics from hanging networkidle-like waits if they ever slip in
    blocklist = list(DEFAULT_BLOCKED_RESOURCES) if not no_default_blocklist else []
    if block_domains:
        blocklist.extend(block_domains)

    async def _route_handler(route):
        url = route.request.url
        if any(p in url for p in blocklist):
            logger.debug(f"Blocking request: {url}")
            await route.abort()
        else:
            await route.continue_()

    await context.route("**/*", _route_handler)

    if tracing:
        await context.tracing.start(screenshots=True, snapshots=True, sources=True)

    page = await context.new_page()
    adapter = PlaywrightAdapter(
        page,
        base_url,
        nav_timeout_ms=nav_timeout_ms,
        action_timeout_ms=action_timeout_ms,
    )

    return browser, context, adapter
