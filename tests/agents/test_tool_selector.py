from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from llm_common.agents.schemas import PlannedTask, SubTask
from llm_common.agents.tool_selector import ToolSelectionConfig, ToolSelector
from llm_common.core.models import LLMResponse, LLMUsage


class _FakeRegistry:
    def get_tools_schema(self) -> str:
        return '[{"name":"t1","description":"d1","parameters":{"type":"object","properties":{}}}]'


@pytest.fixture
def mock_llm_client():
    return AsyncMock()


@pytest.mark.asyncio
async def test_tool_selector_caps_calls(mock_llm_client):
    mock_llm_client.chat_completion.return_value = LLMResponse(
        id="x",
        model="glm-4.5-air",
        content='{"calls": ['
        + ",".join([f'{{"tool":"t{i}","args":{{}},"reasoning":"r"}}' for i in range(7)])
        + "]}",
        finish_reason="stop",
        usage=LLMUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        provider="test",
    )

    selector = ToolSelector(
        mock_llm_client,
        ToolSelectionConfig(model="glm-4.5-air", max_calls=5),
    )
    calls = await selector.select_tool_calls(
        task=PlannedTask(id=1, description="d", sub_tasks=[SubTask(id=1, description="s")]),
        tool_registry=_FakeRegistry(),
    )
    assert len(calls) == 5
    mock_llm_client.chat_completion.assert_called_once()


@pytest.mark.asyncio
async def test_tool_selector_uses_fallback_model_on_network_error(mock_llm_client):
    mock_llm_client.chat_completion.side_effect = [
        Exception("Network error"),
        LLMResponse(
            id="x2",
            model="fallback-model",
            content='{"calls":[{"tool":"t1","args":{},"reasoning":"r"}]}',
            finish_reason="stop",
            usage=LLMUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            provider="test",
        ),
    ]

    selector = ToolSelector(
        mock_llm_client,
        ToolSelectionConfig(
            model="primary-model", fallback_model="fallback-model", max_calls=5
        ),
    )
    calls = await selector.select_tool_calls(
        task=PlannedTask(id=1, description="d", sub_tasks=[SubTask(id=1, description="s")]),
        tool_registry=_FakeRegistry(),
    )
    assert len(calls) == 1
    assert calls[0].tool == "t1"
    assert mock_llm_client.chat_completion.call_count == 2


@pytest.mark.asyncio
async def test_tool_selector_uses_fallback_model_on_parse_error(mock_llm_client):
    mock_llm_client.chat_completion.side_effect = [
        LLMResponse(
            id="x1",
            model="primary-model",
            content="not-json",
            finish_reason="stop",
            usage=LLMUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            provider="test",
        ),
        LLMResponse(
            id="x2",
            model="fallback-model",
            content='{"calls":[{"tool":"t1","args":{},"reasoning":"r"}]}',
            finish_reason="stop",
            usage=LLMUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            provider="test",
        ),
    ]

    selector = ToolSelector(
        mock_llm_client,
        ToolSelectionConfig(
            model="primary-model", fallback_model="fallback-model", max_calls=5
        ),
    )
    calls = await selector.select_tool_calls(
        task=PlannedTask(id=1, description="d", sub_tasks=[SubTask(id=1, description="s")]),
        tool_registry=_FakeRegistry(),
    )
    assert len(calls) == 1
    assert calls[0].tool == "t1"
    assert mock_llm_client.chat_completion.call_count == 2


@pytest.mark.asyncio
async def test_tool_selector_fail_closed_returns_empty_on_total_failure(mock_llm_client):
    mock_llm_client.chat_completion.side_effect = [
        Exception("Network error"),
        LLMResponse(
            id="x2",
            model="fallback-model",
            content="still-not-json",
            finish_reason="stop",
            usage=LLMUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            provider="test",
        ),
    ]

    selector = ToolSelector(
        mock_llm_client,
        ToolSelectionConfig(
            model="primary-model",
            fallback_model="fallback-model",
            max_calls=5,
            fail_closed=True,
        ),
    )
    calls = await selector.select_tool_calls(
        task=PlannedTask(id=1, description="d", sub_tasks=[SubTask(id=1, description="s")]),
        tool_registry=_FakeRegistry(),
    )
    assert calls == []
    assert mock_llm_client.chat_completion.call_count == 2


@pytest.mark.asyncio
async def test_tool_selector_fail_open_returns_empty(mock_llm_client):
    mock_llm_client.chat_completion.side_effect = [
        Exception("Network error"),
        Exception("Another network error"),
    ]

    selector = ToolSelector(
        mock_llm_client,
        ToolSelectionConfig(
            model="primary-model",
            fallback_model="fallback-model",
            max_calls=5,
            fail_closed=False,
        ),
    )
    calls = await selector.select_tool_calls(
        task=PlannedTask(id=1, description="d", sub_tasks=[SubTask(id=1, description="s")]),
        tool_registry=_FakeRegistry(),
    )
    assert calls == []
    assert mock_llm_client.chat_completion.call_count == 2
