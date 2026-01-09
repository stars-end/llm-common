import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Any

from pydantic import BaseModel

from llm_common.agents.callbacks import AgentCallbacks, ToolCallInfo, ToolCallResult
from llm_common.agents.tool_context import ToolContextManager
from llm_common.agents.tool_selector import ToolSelector
from llm_common.core import LLMClient

from .schemas import ExecutionPlan, PlannedTask, SubTaskResult, ToolCall

logger = logging.getLogger(__name__)


class StreamEvent(BaseModel):
    """Event yielded during streaming execution."""

    type: str  # "thinking", "tool_call", "tool_result", "text", "sources", "error"
    data: Any


class AgenticExecutor:
    """
    Port of Dexter's TaskExecutor.
    Executes plans by resolving subtasks to tool calls and running them in parallel.
    """

    def __init__(self, client: LLMClient, tool_registry: Any, context_manager: ToolContextManager):
        self.client = client
        self.registry = tool_registry
        self.context_manager = context_manager

    async def execute_plan(
        self,
        plan: ExecutionPlan,
        query_id: str,
        callbacks: AgentCallbacks | None = None,
    ) -> list[SubTaskResult]:
        """
        Execute an entire plan by running each task sequentially.
        Tools within each task are executed in parallel.
        """
        logger.info(f"Starting execution of plan with {len(plan.tasks)} tasks.")
        all_results = []

        for iteration, task in enumerate(plan.tasks):
            if callbacks and callbacks.on_iteration_start:
                callbacks.on_iteration_start(iteration)

            result = await self.execute_task(task, query_id, callbacks)
            all_results.append(result)

            if callbacks and callbacks.on_iteration_complete:
                callbacks.on_iteration_complete(iteration)

            if not result.success:
                logger.error(f"Execution halted due to failure in task {task.id}")
                break

        return all_results

    async def run_stream(
        self,
        plan: ExecutionPlan,
        query_id: str,
        callbacks: AgentCallbacks | None = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Execute plan as async generator yielding stream events.

        Yields:
            StreamEvent objects for each step of execution:
            - "thinking": Processing status
            - "tool_call": Tool invocation starting
            - "tool_result": Tool result received
            - "sources": All sources at end
            - "error": Any errors encountered
        """
        logger.info(f"Starting streaming execution of plan with {len(plan.tasks)} tasks.")

        for iteration, task in enumerate(plan.tasks):
            if callbacks and callbacks.on_iteration_start:
                callbacks.on_iteration_start(iteration)

            # Yield thinking event
            yield StreamEvent(type="thinking", data=f"Processing: {task.description}")

            if callbacks and callbacks.on_thinking:
                callbacks.on_thinking(task.description)

            try:
                # Resolve tools
                tool_calls = await self._resolve_tools(task)

                if not tool_calls:
                    yield StreamEvent(type="text", data="No tools needed for this step.")
                    continue

                # Notify callbacks about tool calls
                if callbacks and callbacks.on_tool_calls_start:
                    tool_infos = [ToolCallInfo(name=tc.tool, args=tc.args) for tc in tool_calls]
                    callbacks.on_tool_calls_start(tool_infos)

                # Execute each tool and yield results
                for tc in tool_calls:
                    yield StreamEvent(type="tool_call", data={"tool": tc.tool, "args": tc.args})

                    try:
                        result = await self._execute_tool(tc, task.id, query_id)
                        yield StreamEvent(type="tool_result", data=result)

                        if callbacks and callbacks.on_tool_call_complete:
                            callbacks.on_tool_call_complete(
                                ToolCallResult(
                                    name=tc.tool,
                                    args=tc.args,
                                    summary=str(result.get("output", ""))[:200],
                                    success=True,
                                )
                            )
                    except Exception as e:
                        error_data = {"tool": tc.tool, "error": str(e)}
                        yield StreamEvent(type="error", data=error_data)

                        if callbacks and callbacks.on_tool_call_complete:
                            callbacks.on_tool_call_complete(
                                ToolCallResult(
                                    name=tc.tool, args=tc.args, summary=str(e), success=False
                                )
                            )

            except Exception as e:
                logger.error(f"Task {task.id} failed: {e}")
                yield StreamEvent(type="error", data={"task": task.id, "error": str(e)})

            if callbacks and callbacks.on_iteration_complete:
                callbacks.on_iteration_complete(iteration)

        # Yield sources at end (if context manager supports it)
        try:
            if hasattr(self.context_manager, "get_all_sources"):
                sources = self.context_manager.get_all_sources(query_id)
                if sources:
                    yield StreamEvent(type="sources", data=sources)
        except Exception as e:
            logger.warning(f"Could not get sources: {e}")

    async def execute_task(
        self,
        task: PlannedTask,
        query_id: str,
        callbacks: AgentCallbacks | None = None,
    ) -> SubTaskResult:
        """
        Execute a single task:
        1. Resolve subtasks -> Tool Calls (LLM)
        2. Execute Tools (Parallel)
        3. Save Context
        """
        logger.info(f"Executing Task {task.id}: {task.description}")

        if callbacks and callbacks.on_thinking:
            callbacks.on_thinking(task.description)

        try:
            # 1. Generate Tool Calls
            tool_calls = await self._resolve_tools(task)

            if not tool_calls:
                logger.info(f"No tools needed for task {task.id}")
                return SubTaskResult(
                    task_id=task.id, sub_task_id=0, success=True, result="No tools called"
                )

            # 2. Execute Tools
            results = await self.execute_tool_calls(tool_calls, task.id, query_id, callbacks)

            return SubTaskResult(task_id=task.id, sub_task_id=0, success=True, result=results)

        except Exception as e:
            logger.error(f"Task {task.id} failed: {e}")
            return SubTaskResult(task_id=task.id, sub_task_id=0, success=False, error=str(e))

    async def execute_tool_calls(
        self,
        tool_calls: list[ToolCall],
        task_id: int,
        query_id: str,
        callbacks: AgentCallbacks | None = None,
    ) -> list[Any]:
        """
        Executes a list of tool calls in parallel and handles context saving.
        """
        if not tool_calls:
            return []

        # Notify callbacks
        if callbacks and callbacks.on_tool_calls_start:
            tool_infos = [ToolCallInfo(name=tc.tool, args=tc.args) for tc in tool_calls]
            callbacks.on_tool_calls_start(tool_infos)

        # Execute Tools Parallel
        results = await asyncio.gather(
            *[self._execute_tool(tc, task_id, query_id) for tc in tool_calls],
            return_exceptions=True,
        )

        # Notify callbacks of completion
        for tc, result in zip(tool_calls, results):
            if callbacks and callbacks.on_tool_call_complete:
                is_error = isinstance(result, Exception)
                callbacks.on_tool_call_complete(
                    ToolCallResult(
                        name=tc.tool,
                        args=tc.args,
                        summary=str(result)[:200] if not is_error else str(result),
                        success=not is_error,
                    )
                )
        return results

    async def _resolve_tools(self, task: PlannedTask) -> list[ToolCall]:
        selector = ToolSelector(self.client)
        return await selector.select_tool_calls(task=task, tool_registry=self.registry)

    async def _execute_tool(self, call: ToolCall, task_id: int, query_id: str) -> Any:
        try:
            logger.info(f"Calling tool: {call.tool}")
            # Support both registry.execute(tool_name, args_dict) and registry.execute(tool_name, **kwargs).
            # Different call sites in llm-common and downstream repos use different conventions.
            try:
                result = await self.registry.execute(call.tool, call.args)
            except TypeError:
                result = await self.registry.execute(call.tool, **call.args)

            # Save Context
            await self.context_manager.save_context(
                tool_name=call.tool,
                args=call.args,
                result=result,
                task_id=str(task_id),
                query_id=query_id,
            )

            return {"tool": call.tool, "args": call.args, "output": result}
        except Exception as e:
            logger.error(f"Tool execution {call.tool} failed: {e}")
            return {"tool": call.tool, "error": str(e)}
