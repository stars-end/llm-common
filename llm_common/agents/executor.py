import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Optional, Protocol

# from .tool_context import ToolContextManager # Assumed to exist or we mock it for now
from llm_common.agents.tool_context import ToolContextManager  # It exists in file list
from llm_common.core import LLMClient, LLMMessage

from .schemas import ExecutionPlan, PlannedTask, SubTaskResult, ToolCall

logger = logging.getLogger(__name__)


@dataclass
class StreamEvent:
    """
    Event yielded during streaming execution.
    
    Types:
        - "thinking": Agent reasoning about the task
        - "tool_call": Tool invocation started
        - "tool_result": Tool returned output
        - "text": Streaming answer text
        - "sources": Final source list
        - "error": Error occurred
    """
    type: str
    data: Any = None
    task_id: Optional[int] = None
    tool_name: Optional[str] = None


class AgentCallbacks(Protocol):
    """Protocol for agent callbacks (optional)."""
    def on_agent_start(self, name: str, query: str) -> None: ...
    def on_agent_finish(self, name: str, output: Any) -> None: ...
    def on_tool_start(self, tool_name: str, args: dict) -> None: ...
    def on_tool_finish(self, tool_name: str, output: Any, task_id: str | None = None, query_id: str | None = None) -> None: ...
    def on_thought_start(self) -> None: ...
    def on_thought_finish(self, thought: str) -> None: ...


class AgenticExecutor:
    """
    Port of Dexter's TaskExecutor.
    Executes plans by resolving subtasks to tool calls and running them in parallel.
    """

    def __init__(self, client: LLMClient, tool_registry: Any, context_manager: ToolContextManager):
        self.client = client
        self.registry = tool_registry
        self.context_manager = context_manager

    async def execute_plan(self, plan: ExecutionPlan, query_id: str) -> list[SubTaskResult]:
        """
        Execute an entire plan by running each task sequentially.
        Tools within each task are executed in parallel.
        """
        logger.info(f"Starting execution of plan with {len(plan.tasks)} tasks.")
        all_results = []

        for task in plan.tasks:
            result = await self.execute_task(task, query_id)
            all_results.append(result)

            if not result.success:
                logger.error(f"Execution halted due to failure in task {task.id}")
                break

        return all_results

    async def execute_task(self, task: PlannedTask, query_id: str) -> SubTaskResult:
        """
        Execute a single task:
        1. Resolve subtasks -> Tool Calls (LLM)
        2. Execute Tools (Parallel)
        3. Save Context
        """
        logger.info(f"Executing Task {task.id}: {task.description}")

        try:
            # 1. Generate Tool Calls
            tool_calls = await self._resolve_tools(task)

            if not tool_calls:
                logger.info(f"No tools needed for task {task.id}")
                return SubTaskResult(
                    task_id=task.id, sub_task_id=0, success=True, result="No tools called"
                )

            # 2. Execute Tools Parallel
            results = await asyncio.gather(
                *[self._execute_tool(tc, task.id, query_id) for tc in tool_calls],
                return_exceptions=True,
            )

            return SubTaskResult(task_id=task.id, sub_task_id=0, success=True, result=results)

        except Exception as e:
            logger.error(f"Task {task.id} failed: {e}")
            return SubTaskResult(task_id=task.id, sub_task_id=0, success=False, error=str(e))

    async def _resolve_tools(self, task: PlannedTask) -> list[ToolCall]:
        """Ask LLM which tools to call for the subtasks."""

        subtasks_str = "\n".join([f"- {st.description}" for st in task.sub_tasks])
        tools_schema = self.registry.get_tools_schema()  # Assumed method on registry

        # System message: context and instructions
        system_prompt = f"""You are an expert agent execution engine.

        Available Tools:
        {tools_schema}

        Return a JSON list of tool calls to satisfy the given subtasks.
        """

        from pydantic import BaseModel

        # Pydantic schema for list of tool calls
        class ToolCallList(BaseModel):
            calls: list[ToolCall]

        system_prompt += f"\n\nReturn JSON matching: {ToolCallList.model_json_schema()}"

        # User message: the actual task and subtasks to process
        user_prompt = f"""Task: {task.description}

        Subtasks to complete:
        {subtasks_str}

        Decide which tools to call to satisfy these subtasks."""

        response = await self.client.chat_completion(
            messages=[
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=user_prompt),
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )

        content = response.content
        # Basic cleanup
        if content.startswith("```json"):
            content = content[7:-3]

        try:
            tcl = ToolCallList.model_validate_json(content)
            return tcl.calls
        except Exception as e:
            logger.error(f"Tool resolution failed: {e}. Content: {content}")
            return []

    async def _execute_tool(self, call: ToolCall, task_id: int, query_id: str) -> Any:
        try:
            logger.info(f"Calling tool: {call.tool}")
            result = await self.registry.execute(call.tool, call.args)

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

    async def run_stream(
        self,
        plan: ExecutionPlan,
        query_id: str,
        callbacks: Optional[AgentCallbacks] = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Execute plan as async generator yielding stream events.
        
        This is the SSE-compatible entry point for Deep Chat UI.
        Each step yields a StreamEvent that can be serialized to JSON
        and sent over Server-Sent Events.
        
        Args:
            plan: The execution plan to run
            query_id: Unique identifier for this query
            callbacks: Optional callbacks for observability
            
        Yields:
            StreamEvent: Events for thinking, tool_call, tool_result, sources
        """
        logger.info(f"Starting streaming execution of plan with {len(plan.tasks)} tasks.")
        
        # Notify start
        if callbacks:
            try:
                callbacks.on_agent_start("executor", query_id)
            except Exception:
                pass  # Callbacks are optional
        
        all_sources: list[str] = []
        
        for task in plan.tasks:
            # Yield thinking event
            yield StreamEvent(
                type="thinking",
                data={"message": f"Processing: {task.description}"},
                task_id=task.id,
            )
            
            if callbacks:
                try:
                    callbacks.on_thought_start()
                except Exception:
                    pass
            
            try:
                # Resolve tools
                tool_calls = await self._resolve_tools(task)
                
                if callbacks:
                    try:
                        callbacks.on_thought_finish(f"Resolved {len(tool_calls)} tool calls")
                    except Exception:
                        pass
                
                if not tool_calls:
                    yield StreamEvent(
                        type="thinking",
                        data={"message": "No tools needed for this task"},
                        task_id=task.id,
                    )
                    continue
                
                # Execute each tool and yield events
                for tc in tool_calls:
                    # Yield tool_call event
                    yield StreamEvent(
                        type="tool_call",
                        data={"tool": tc.tool, "args": tc.args},
                        task_id=task.id,
                        tool_name=tc.tool,
                    )
                    
                    if callbacks:
                        try:
                            callbacks.on_tool_start(tc.tool, tc.args)
                        except Exception:
                            pass
                    
                    # Execute tool
                    result = await self._execute_tool(tc, task.id, query_id)
                    
                    # Collect sources from result
                    if isinstance(result, dict):
                        output = result.get("output")
                        if hasattr(output, "source_urls"):
                            all_sources.extend(output.source_urls)
                        elif isinstance(output, dict) and "source_urls" in output:
                            all_sources.extend(output.get("source_urls", []))
                    
                    # Yield tool_result event
                    yield StreamEvent(
                        type="tool_result",
                        data=result,
                        task_id=task.id,
                        tool_name=tc.tool,
                    )
                    
                    if callbacks:
                        try:
                            callbacks.on_tool_finish(tc.tool, result, str(task.id), query_id)
                        except Exception:
                            pass
                            
            except Exception as e:
                logger.error(f"Task {task.id} failed during stream: {e}")
                yield StreamEvent(
                    type="error",
                    data={"error": str(e), "task_id": task.id},
                    task_id=task.id,
                )
        
        # Yield sources at end (deduplicated)
        unique_sources = list(dict.fromkeys(all_sources))
        if unique_sources:
            yield StreamEvent(
                type="sources",
                data={"sources": unique_sources},
            )
        
        # Notify finish
        if callbacks:
            try:
                callbacks.on_agent_finish("executor", None)
            except Exception:
                pass
        
        logger.info(f"Streaming execution complete. Collected {len(unique_sources)} sources.")

