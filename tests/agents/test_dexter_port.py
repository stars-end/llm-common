from unittest.mock import AsyncMock, MagicMock

import pytest

from llm_common.agents.executor import AgenticExecutor
from llm_common.agents.planner import TaskPlanner
from llm_common.agents.schemas import ExecutionPlan, PlannedTask, SubTask
from llm_common.agents.tool_context import ToolContextManager


@pytest.mark.asyncio
async def test_planner_generates_plan():
    # Mock LLM Client
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = """
    {
        "tasks": [
            {
                "id": 1,
                "description": "Research Apple",
                "sub_tasks": [
                    {"id": 1, "description": "Get stock price"}
                ]
            }
        ]
    }
    """
    mock_client.chat_completion = AsyncMock(return_value=mock_response)

    planner = TaskPlanner(mock_client)
    plan = await planner.plan("Analyze Apple")

    assert len(plan.tasks) == 1
    assert plan.tasks[0].description == "Research Apple"
    assert plan.tasks[0].sub_tasks[0].description == "Get stock price"


@pytest.mark.asyncio
async def test_executor_runs_tools():
    # Mock LLM Client for tool resolution
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = """
    {
        "calls": [
            {"tool": "get_price", "args": {"ticker": "AAPL"}, "reasoning": "Need price"}
        ]
    }
    """
    mock_client.chat_completion = AsyncMock(return_value=mock_response)

    # Mock Tool Registry
    mock_registry = MagicMock()
    mock_registry.get_tools_schema.return_value = "Tools..."
    mock_registry.execute = AsyncMock(return_value=150.0)

    # Mock Context Manager
    mock_ctx = AsyncMock(spec=ToolContextManager)

    executor = AgenticExecutor(mock_client, mock_registry, mock_ctx)

    task = PlannedTask(id=1, description="Task 1", sub_tasks=[SubTask(id=1, description="sub")])

    result = await executor.execute_task(task, "q-1")

    assert result.success is True
    assert result.task_id == 1
    # Check tool was executed
    mock_registry.execute.assert_called_with("get_price", {"ticker": "AAPL"})
    # Check context saved
    mock_ctx.save_context.assert_called()


@pytest.mark.asyncio
async def test_executor_runs_plan():
    # Mock LLM Client
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = '{"calls": [{"tool": "test", "args": {}, "reasoning": "rsn"}]}'
    mock_client.chat_completion = AsyncMock(return_value=mock_response)

    # Mock Registry
    mock_registry = MagicMock()
    mock_registry.get_tools_schema.return_value = "{}"
    mock_registry.execute = AsyncMock(return_value="ok")

    # Mock Context Manager
    mock_ctx = AsyncMock(spec=ToolContextManager)

    executor = AgenticExecutor(mock_client, mock_registry, mock_ctx)

    plan = ExecutionPlan(
        tasks=[
            PlannedTask(id=1, description="Task 1", sub_tasks=[SubTask(id=1, description="st")]),
            PlannedTask(id=2, description="Task 2", sub_tasks=[SubTask(id=2, description="st")]),
        ]
    )

    results = await executor.execute_plan(plan, "q-1")

    assert len(results) == 2
    assert results[0].task_id == 1
    assert results[1].task_id == 2
    assert mock_registry.execute.call_count == 2
