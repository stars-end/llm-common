from unittest.mock import AsyncMock, MagicMock

import pytest

from llm_common.agents.orchestrator import IterativeOrchestrator
from llm_common.agents.provenance import Evidence, EvidenceEnvelope
from llm_common.agents.tools import BaseTool, ToolMetadata, ToolRegistry, ToolResult


class MockTool(BaseTool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(name="mock_tool", description="A mock tool", parameters=[])

    async def execute(self, **kwargs) -> ToolResult:
        ev = Evidence(kind="internal", label="Mock", content="Data")
        envelope = EvidenceEnvelope(evidence=[ev], source_tool="mock_tool")
        return ToolResult(success=True, data="Mock Result", evidence=[envelope])

@pytest.fixture
def mock_client():
    client = MagicMock()
    # Mock Understand phase
    understand_resp = MagicMock()
    understand_resp.content = '{"intent": "test", "entities": ["a"]}'
    client.chat_completion = AsyncMock(return_value=understand_resp)

    # Mock Planner
    plan_resp = MagicMock()
    plan_resp.content = '{"tasks": [{"id": 1, "description": "T1", "sub_tasks": [{"id": 1, "description": "ST1"}]}]}'

    # Mock Executor (tool calls)
    executor_resp = MagicMock()
    executor_resp.content = '{"calls": [{"tool": "mock_tool", "args": {}, "reasoning": "R"}]}'

    # Mock Reflect (complete)
    reflect_resp = MagicMock()
    reflect_resp.content = '{"is_complete": true, "reasoning": "Done"}'

    # Mock Synthesizer
    synth_resp = MagicMock()
    synth_resp.content = 'Final Answer'

    # Setup sequential side effects for chat_completion
    client.chat_completion.side_effect = [
        understand_resp, # UnderstandPhase
        plan_resp,       # TaskPlanner
        executor_resp,   # AgenticExecutor
        reflect_resp,    # ReflectPhase
        synth_resp       # AnswerSynthesizer (if called)
    ]

    # Mock generate_structured for Synthesizer
    client.generate_structured = AsyncMock(return_value="Final Answer")
    client.generate = AsyncMock(return_value="Final Answer")

    return client

@pytest.fixture
def registry():
    reg = ToolRegistry()
    reg.register(MockTool())
    return reg

@pytest.mark.asyncio
async def test_orchestrator_run_success(mock_client, registry, tmp_path):
    orchestrator = IterativeOrchestrator(
        llm_client=mock_client,
        tool_registry=registry,
        work_dir=tmp_path,
        max_iterations=2
    )

    result = await orchestrator.run("Test query")

    assert result.answer == "Final Answer"
    assert result.iterations == 1
    assert len(result.evidence_envelope["evidence"]) > 0

@pytest.mark.asyncio
async def test_orchestrator_run_stream(mock_client, registry, tmp_path):
    orchestrator = IterativeOrchestrator(
        llm_client=mock_client,
        tool_registry=registry,
        work_dir=tmp_path,
        max_iterations=1
    )

    events = []
    async for event in orchestrator.run_stream("Test query"):
        events.append(event)

    # Check for expected events
    event_types = [e.type for e in events]
    assert "understanding" in event_types
    assert "plan" in event_types
    assert "tool_call" in event_types
    assert "tool_result" in event_types
    assert "evidence" in event_types
    assert "answer" in event_types

@pytest.mark.asyncio
async def test_orchestrator_max_iterations(mock_client, registry, tmp_path):
    # Setup mocks to force 2 iterations then finish
    reflect_incomplete = MagicMock()
    reflect_incomplete.content = '{"is_complete": false, "reasoning": "More"}'

    reflect_complete = MagicMock()
    reflect_complete.content = '{"is_complete": true, "reasoning": "Done"}'

    # Re-setup side effects
    mock_client.chat_completion.side_effect = [
        MagicMock(content='{"intent": "test", "entities": []}'), # Understand
        MagicMock(content='{"tasks": [{"id": 1, "description": "T1"}]}'), # Plan 1
        MagicMock(content='{"calls": []}'), # Execute 1
        reflect_incomplete, # Reflect 1 -> Incomplete
        MagicMock(content='{"tasks": [{"id": 2, "description": "T2"}]}'), # Plan 2
        MagicMock(content='{"calls": []}'), # Execute 2
        reflect_complete, # Reflect 2 -> Complete
        MagicMock(content='Final Answer') # Synth
    ]

    orchestrator = IterativeOrchestrator(
        llm_client=mock_client,
        tool_registry=registry,
        work_dir=tmp_path,
        max_iterations=2
    )

    result = await orchestrator.run("Test query")
    assert result.iterations == 2
