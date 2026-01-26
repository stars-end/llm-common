import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from llm_common.agents.runtime.runtime import AgentRuntime
from llm_common.agents.schemas import ExecutionPlan, PlannedTask, SubTask, ToolCall
from llm_common.agents.synthesizer import StructuredAnswer


class TestAgentRuntime(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.mock_tool_registry = MagicMock()
        self.mock_context_manager = MagicMock()

    def test_run_happy_path(self):
        # Arrange
        runtime = AgentRuntime(
            client=self.mock_client,
            tool_registry=self.mock_tool_registry,
            context_manager=self.mock_context_manager,
        )

        runtime.planner.plan = AsyncMock(
            return_value=ExecutionPlan(
                tasks=[
                    PlannedTask(
                        id=1,
                        description="Test task",
                        sub_tasks=[SubTask(id=1, description="Test subtask")],
                    )
                ]
            )
        )
        runtime.tool_selector.select_tool_calls = AsyncMock(
            return_value=[ToolCall(tool="test_tool", args={}, reasoning="testing")]
        )
        runtime.executor.execute_tool_calls = AsyncMock(return_value=[{"output": "tool result"}])
        runtime.synthesizer.synthesize = AsyncMock(
            return_value=StructuredAnswer(content="Final answer", sources=[])
        )

        # Act
        result = asyncio.run(runtime.run(query="test query"))

        # Assert
        self.assertEqual(result.content, "Final answer")
        runtime.executor.execute_tool_calls.assert_called_once()
        self.assertEqual(len(runtime.executor.execute_tool_calls.call_args[0][0]), 1)

    def test_run_max_calls_limit(self):
        # Arrange
        runtime = AgentRuntime(
            client=self.mock_client,
            tool_registry=self.mock_tool_registry,
            context_manager=self.mock_context_manager,
            max_calls=2,
        )

        runtime.planner.plan = AsyncMock(
            return_value=ExecutionPlan(
                tasks=[
                    PlannedTask(
                        id=1,
                        description="Task 1",
                        sub_tasks=[SubTask(id=1, description="Subtask 1")],
                    )
                ]
            )
        )
        runtime.tool_selector.select_tool_calls = AsyncMock(
            return_value=[
                ToolCall(tool="test_tool_1", args={}, reasoning="testing"),
                ToolCall(tool="test_tool_2", args={}, reasoning="testing"),
                ToolCall(tool="test_tool_3", args={}, reasoning="testing"),
            ]
        )
        runtime.executor.execute_tool_calls = AsyncMock(return_value=[])
        runtime.synthesizer.synthesize = AsyncMock(
            return_value=StructuredAnswer(content="Final answer", sources=[])
        )

        # Act
        asyncio.run(runtime.run(query="test query"))

        # Assert
        runtime.executor.execute_tool_calls.assert_called_once()
        self.assertEqual(len(runtime.executor.execute_tool_calls.call_args[0][0]), 2)


if __name__ == "__main__":
    unittest.main()
