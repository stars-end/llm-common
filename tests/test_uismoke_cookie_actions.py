from unittest.mock import AsyncMock, MagicMock

import pytest

from llm_common.agents.ui_smoke_agent import UISmokeAgent


@pytest.mark.asyncio
async def test_deterministic_set_cookie_action():
    browser = MagicMock()
    browser.set_cookie = AsyncMock()
    llm = MagicMock()

    agent = UISmokeAgent(glm_client=llm, browser=browser, base_url="https://example.com")
    actions = []

    step_data = {
        "action": "set_cookie",
        "name": "x-test-user",
        "value": "token-value",
        "domain": "auto",
        "path": "/",
        "same_site": "Lax",
    }

    success = await agent._execute_deterministic_step(step_data, actions)

    assert success is True
    browser.set_cookie.assert_awaited_once_with(
        name="x-test-user",
        value="token-value",
        domain=None,
        path="/",
        secure=None,
        same_site="Lax",
    )
    assert actions[0]["tool"] == "set_cookie"
    assert actions[0]["args"]["value"] == "[REDACTED]"


@pytest.mark.asyncio
async def test_deterministic_clear_cookies_action():
    browser = MagicMock()
    browser.clear_cookies = AsyncMock()
    llm = MagicMock()

    agent = UISmokeAgent(glm_client=llm, browser=browser, base_url="https://example.com")
    actions = []

    success = await agent._execute_deterministic_step({"action": "clear_cookies"}, actions)

    assert success is True
    browser.clear_cookies.assert_awaited_once()
    assert actions[0]["tool"] == "clear_cookies"
