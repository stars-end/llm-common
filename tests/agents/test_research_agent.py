from unittest.mock import AsyncMock, MagicMock

import pytest

from llm_common.agents.research_agent import ResearchAgent
from llm_common.agents.schemas import ExecutionPlan, PlannedTask, SubTask, SubTaskResult


@pytest.mark.asyncio
async def test_research_agent_flow():
    # Mock Clients
    mock_llm = MagicMock()
    mock_search = MagicMock()
    mock_search.search = AsyncMock(return_value=MagicMock(model_dump=lambda: {"results": []}))

    # Create Agent
    # We need to mock planner and executor mostly to avoid full LLM calls
    agent = ResearchAgent(mock_llm, mock_search, work_dir="/tmp/test_agent")

    # Mock Planner Response
    mock_plan = ExecutionPlan(
        tasks=[
            PlannedTask(
                id=1,
                description="Research Test",
                sub_tasks=[SubTask(id=1, description="Search Google")],
            )
        ]
    )
    agent.planner.plan = AsyncMock(return_value=mock_plan)

    # Mock Executor Response
    mock_result = SubTaskResult(
        task_id=1,
        sub_task_id=0,
        success=True,
        result={"tool": "web_search", "output": {"results": []}},
    )
    agent.executor.execute_plan = AsyncMock(return_value=[mock_result])

    # Run
    result = await agent.run("bill-123", "some text", "San Jose")

    # Verify
    assert result["status"] == "success"
    assert result["run_id"] is not None
    assert agent.planner.plan.called
    assert agent.executor.execute_plan.called
