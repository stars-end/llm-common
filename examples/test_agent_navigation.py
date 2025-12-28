#!/usr/bin/env python3
"""Test GLM-4.6V agent's ability to navigate and fill forms.

This is a simple validation test that:
1. Launches a real browser
2. Uses GLM-4.6V to search Google for "nikon cameras"
3. Verifies the agent can navigate, fill forms, and click buttons

Run with:
    export ZAI_API_KEY="your-key"
    python test_agent_navigation.py
"""

import asyncio
import base64
import logging
import os
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from llm_common import GLMClient, GLMConfig
from llm_common.agents import Story, StoryStep, UISmokeAgent

logging.basicConfig(
    level=logging.DEBUG,  # Enable debug for detailed logs
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class SimpleBrowserAdapter:
    """Minimal Playwright adapter for testing."""

    def __init__(self, page, base_url: str):
        self.page = page
        self.base_url = base_url
        self._console_errors = []
        self._network_errors = []
        self._setup_listeners()

    def _setup_listeners(self):
        def on_console(msg):
            if msg.type in ("error", "warning"):
                self._console_errors.append(f"[{msg.type}] {msg.text}")

        def on_response(response):
            if response.status >= 400:
                self._network_errors.append({
                    "url": response.url,
                    "status": response.status,
                    "method": response.request.method,
                })

        self.page.on("console", on_console)
        self.page.on("response", on_response)

    async def navigate(self, path: str):
        from llm_common.agents import NavigationError

        # For this test, treat path as full URL if it starts with http
        if path.startswith("http"):
            url = path
        else:
            url = f"{self.base_url}{path}"

        logger.info(f"Navigating to {url}")
        try:
            await self.page.goto(url, wait_until="networkidle", timeout=30000)
        except Exception as e:
            raise NavigationError(f"Navigation failed: {e}")

    async def click(self, target: str):
        from llm_common.agents import ElementNotFoundError

        logger.info(f"Clicking: {target}")
        try:
            # Try as selector first
            if not target.startswith("text="):
                try:
                    await self.page.click(target, timeout=5000)
                    return
                except Exception:
                    pass

            # Try as text
            selector = target if target.startswith("text=") else f"text={target}"
            await self.page.click(selector, timeout=5000)
        except Exception as e:
            raise ElementNotFoundError(f"Click failed for {target}: {e}")

    async def type_text(self, selector: str, text: str):
        from llm_common.agents import ElementNotFoundError

        logger.info(f"Typing '{text}' into {selector}")
        try:
            await self.page.fill(selector, text, timeout=5000)
        except Exception as e:
            raise ElementNotFoundError(f"Type failed: {e}")

    async def screenshot(self) -> str:
        # PNG doesn't support quality parameter
        screenshot_bytes = await self.page.screenshot(type="png")
        screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
        size_kb = len(screenshot_bytes) / 1024
        logger.debug(f"Screenshot: {size_kb:.1f} KB")
        return screenshot_b64

    async def get_console_errors(self) -> list[str]:
        errors = self._console_errors.copy()
        self._console_errors.clear()
        return errors

    async def get_network_errors(self) -> list[dict]:
        errors = self._network_errors.copy()
        self._network_errors.clear()
        return errors

    async def wait_for_selector(self, selector: str, timeout_ms: int = 5000):
        await self.page.wait_for_selector(selector, timeout=timeout_ms)

    async def get_current_url(self) -> str:
        return self.page.url

    async def close(self):
        await self.page.close()


async def main():
    """Run Google search test."""
    api_key = os.environ.get("ZAI_API_KEY")
    if not api_key:
        logger.error("ZAI_API_KEY not set")
        sys.exit(1)

    logger.info("="*60)
    logger.info("Testing GLM-4.6V Agent Navigation & Form Filling")
    logger.info("="*60)

    # Create a simple test story
    story = Story(
        id="test-google-search",
        persona="User searching for camera information",
        steps=[
            StoryStep(
                id="step-1-navigate",
                description=(
                    "Navigate to https://www.google.com. "
                    "Verify the Google homepage loads."
                ),
                exploration_budget=0,
            ),
            StoryStep(
                id="step-2-search",
                description=(
                    "Find the search box on the Google homepage. "
                    "Type 'nikon cameras' into the search box. "
                    "Click the search button or press enter. "
                    "Verify search results appear."
                ),
                exploration_budget=1,
            ),
        ],
    )

    # Initialize GLM client
    logger.info("Initializing GLM-4.6V client...")
    glm_config = GLMConfig(api_key=api_key, default_model="glm-4.6v")
    glm_client = GLMClient(glm_config)

    # Launch browser
    logger.info("Launching Playwright browser...")
    from playwright.async_api import async_playwright

    playwright = await async_playwright().start()
    headless = os.environ.get("HEADLESS", "true").lower() == "true"
    browser = await playwright.chromium.launch(headless=headless)
    context = await browser.new_context(
        viewport={"width": 1280, "height": 800},
    )
    page = await context.new_page()

    # Create adapter
    adapter = SimpleBrowserAdapter(page, "https://www.google.com")

    # Create agent
    agent = UISmokeAgent(
        glm_client=glm_client,
        browser=adapter,
        base_url="https://www.google.com",
        max_tool_iterations=15,  # Give it more iterations for this test
    )

    # Run story
    logger.info("\nRunning test story...")
    logger.info("="*60)

    try:
        result = await agent.run_story(story)

        logger.info("\n" + "="*60)
        logger.info("Test Results")
        logger.info("="*60)
        logger.info(f"Story status: {result.status}")
        logger.info(f"Steps completed: {len(result.step_results)}/{len(story.steps)}")

        for step_result in result.step_results:
            logger.info(f"\nStep: {step_result.step_id}")
            logger.info(f"  Status: {step_result.status}")
            logger.info(f"  Actions taken: {len(step_result.actions_taken)}")
            for action in step_result.actions_taken:
                logger.info(f"    - {action['tool']}({action['args']})")

            if step_result.errors:
                logger.warning(f"  Errors: {len(step_result.errors)}")
                for error in step_result.errors:
                    logger.warning(f"    [{error.severity}] {error.message}")

        logger.info(f"\nTotal errors: {len(result.errors)}")

        # Check if we succeeded
        if result.status == "pass":
            logger.info("\n✅ TEST PASSED: Agent successfully navigated and filled forms!")
            logger.info("   - Loaded Google homepage")
            logger.info("   - Found and filled search box")
            logger.info("   - Clicked search button")
            logger.info("   - Verified results appeared")
            exit_code = 0
        else:
            logger.error("\n❌ TEST FAILED: Agent could not complete the task")
            for error in result.errors:
                logger.error(f"   [{error.severity}] {error.type}: {error.message}")
            exit_code = 1

    except Exception:
        logger.exception("Test failed with exception")
        exit_code = 1
    finally:
        # Give user time to see results
        logger.info("\nClosing browser in 5 seconds...")
        await asyncio.sleep(5)
        await browser.close()
        await playwright.stop()

    logger.info("="*60)
    sys.exit(exit_code)


if __name__ == "__main__":
    asyncio.run(main())
