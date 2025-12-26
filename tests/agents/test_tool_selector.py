from unittest.mock import AsyncMock

import pytest

from llm_common.agents.schemas import PlannedTask, SubTask
from llm_common.agents.tool_selector import ToolSelectionConfig, ToolSelector
from llm_common.core.models import LLMResponse, LLMUsage


class _FakeRegistry:
    def get_tools_schema(self) -> str:
        return '[{"name":"t1","description":"d1","parameters":{"type":"object","properties":{}}}]'


@pytest.mark.asyncio
async def test_tool_selector_caps_calls():
    client = AsyncMock()
    client.chat_completion.return_value = LLMResponse(
        id="x",
        model="glm-4.5-air",
        content='{"calls": ['
        + ",".join(
            [f'{{"tool":"t{i}","args":{{}},"reasoning":"r"}}' for i in range(7)]
        )
        + "]}",
        finish_reason="stop",
        usage=LLMUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        provider="test",
    )

    selector = ToolSelector(
        client,
        ToolSelectionConfig(model="glm-4.5-air", max_calls=5),
    )
    calls = await selector.select_tool_calls(
        task=PlannedTask(id=1, description="d", sub_tasks=[SubTask(id=1, description="s")]),
        tool_registry=_FakeRegistry(),
    )
    assert len(calls) == 5


@pytest.mark.asyncio
async def test_tool_selector_uses_fallback_model_on_parse_error():
    client = AsyncMock()
    client.chat_completion.side_effect = [
        LLMResponse(
            id="x1",
            model="glm-4.5-air",
            content="not-json",
            finish_reason="stop",
            usage=LLMUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            provider="test",
        ),
        LLMResponse(
            id="x2",
            model="glm-4.5-air",
            content='{"calls":[{"tool":"t1","args":{},"reasoning":"r"}]}',
            finish_reason="stop",
            usage=LLMUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            provider="test",
        ),
    ]

    selector = ToolSelector(
        client,
        ToolSelectionConfig(model="glm-4.5-air", fallback_model="glm-4.5-air", max_calls=5),
    )
    calls = await selector.select_tool_calls(
        task=PlannedTask(id=1, description="d", sub_tasks=[SubTask(id=1, description="s")]),
        tool_registry=_FakeRegistry(),
    )
    assert len(calls) == 1
    assert calls[0].tool == "t1"


@pytest.mark.asyncio
async def test_tool_selector_fail_closed_returns_empty_on_total_failure():
    client = AsyncMock()
    client.chat_completion.side_effect = [
        LLMResponse(
            id="x1",
            model="glm-4.5-air",
            content="not-json",
            finish_reason="stop",
            usage=LLMUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            provider="test",
        ),
        LLMResponse(
            id="x2",
            model="glm-4.5-air",
            content="still-not-json",
            finish_reason="stop",
            usage=LLMUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            provider="test",
        ),
    ]

    selector = ToolSelector(
        client,
        ToolSelectionConfig(
            model="glm-4.5-air",
            fallback_model="glm-4.5-air",
            max_calls=5,
            fail_closed=True,
        ),
    )
    calls = await selector.select_tool_calls(
        task=PlannedTask(id=1, description="d", sub_tasks=[SubTask(id=1, description="s")]),
        tool_registry=_FakeRegistry(),
    )
    assert calls == []
