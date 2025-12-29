import logging
import uuid
from typing import Any

from llm_common.agents.executor import AgenticExecutor
from llm_common.agents.planner import TaskPlanner
from llm_common.agents.synthesizer import AnswerSynthesizer, StructuredAnswer
from llm_common.agents.tool_context import ToolContextManager
from llm_common.agents.tool_selector import ToolSelector
from llm_common.core import LLMClient

logger = logging.getLogger(__name__)


class AgentRuntime:
    """
    A stable runtime for executing agentic workflows.

    This class orchestrates the planning, tool selection, and execution phases
    of a user query.
    """

    def __init__(
        self,
        client: LLMClient,
        tool_registry: Any,  # Should be ToolRegistry from a future PR
        context_manager: ToolContextManager,
        max_calls: int = 10,
    ):
        """
        Initializes the AgentRuntime.

        Args:
            client: An LLMClient instance for making API calls.
            tool_registry: A registry providing available tools.
            context_manager: Manages the context for tool calls.
            max_calls: The maximum number of tool calls allowed per run.
        """
        self.client = client
        self.tool_registry = tool_registry
        self.context_manager = context_manager
        self.max_calls = max_calls
        self.planner = TaskPlanner(client=client)
        self.executor = AgenticExecutor(
            client=client,
            tool_registry=tool_registry,
            context_manager=context_manager,
        )
        self.synthesizer = AnswerSynthesizer(llm_client=client)
        self.tool_selector = ToolSelector(client=client)

    def _available_tools_summary(self) -> list[dict[str, str]]:
        if hasattr(self.tool_registry, "list_tools"):
            tools = self.tool_registry.list_tools()
            if isinstance(tools, list):
                return [t for t in tools if isinstance(t, dict)]

        if hasattr(self.tool_registry, "get_tools_schema"):
            import json

            schema = self.tool_registry.get_tools_schema()
            if isinstance(schema, str):
                try:
                    parsed = json.loads(schema)
                    if isinstance(parsed, list):
                        summary: list[dict[str, str]] = []
                        for item in parsed:
                            if not isinstance(item, dict):
                                continue
                            name = item.get("name")
                            desc = item.get("description")
                            if isinstance(name, str) and isinstance(desc, str):
                                summary.append({"name": name, "description": desc})
                        return summary
                except Exception:
                    return []
        return []

    @staticmethod
    def _tool_results_to_collected_data(results: list[Any]) -> list[dict[str, Any]]:
        collected: list[dict[str, Any]] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            tool_name = item.get("tool") if isinstance(item.get("tool"), str) else "unknown"
            output = item.get("output")
            source_urls: list[str] = []
            if hasattr(output, "source_urls") and isinstance(getattr(output, "source_urls"), list):
                source_urls = [u for u in getattr(output, "source_urls") if isinstance(u, str)]
            elif isinstance(output, dict) and isinstance(output.get("source_urls"), list):
                source_urls = [u for u in output["source_urls"] if isinstance(u, str)]
            collected.append({"tool_name": tool_name, "data": output, "source_urls": source_urls})
        return collected

    async def run(self, query: str, *, query_id: str | None = None) -> StructuredAnswer:
        """
        Executes a user query and returns a structured answer.
        """
        run_query_id = query_id or str(uuid.uuid4())
        plan = await self.planner.plan(
            query=query, available_tools=self._available_tools_summary() or None
        )

        if not plan.tasks:
            return StructuredAnswer(content="I could not create a plan to answer your query.", sources=[])

        total_calls = 0
        all_results: list[Any] = []

        for task in plan.tasks:
            if total_calls >= self.max_calls:
                logger.warning(f"Max tool calls ({self.max_calls}) reached. Halting execution.")
                break

            tool_calls = await self.tool_selector.select_tool_calls(task=task, tool_registry=self.tool_registry)

            if not tool_calls:
                continue

            calls_to_execute = tool_calls[:self.max_calls - total_calls]

            if len(calls_to_execute) < len(tool_calls):
                logger.warning(f"Max calls reached. Truncating tool calls for task {task.id}.")

            task_results = await self.executor.execute_tool_calls(
                calls_to_execute, task.id, run_query_id
            )
            all_results.extend(task_results)
            total_calls += len(calls_to_execute)

        # Synthesize the final answer
        collected_data = self._tool_results_to_collected_data(all_results)
        final_answer = await self.synthesizer.synthesize(query=query, collected_data=collected_data)
        return final_answer
