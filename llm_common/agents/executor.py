import asyncio
import logging
from typing import List, Dict, Any
from .schemas import PlannedTask, SubTaskResult, ToolCall, ExecutionPlan
from llm_common.core import LLMClient, LLMMessage
# from .tool_context import ToolContextManager # Assumed to exist or we mock it for now
from llm_common.agents.tool_context import ToolContextManager # It exists in file list

logger = logging.getLogger(__name__)

class AgenticExecutor:
    """
    Port of Dexter's TaskExecutor.
    Executes plans by resolving subtasks to tool calls and running them in parallel.
    """

    def __init__(self, client: LLMClient, tool_registry: Any, context_manager: ToolContextManager):
        self.client = client
        self.registry = tool_registry
        self.context_manager = context_manager

    async def execute_plan(self, plan: ExecutionPlan, query_id: str) -> List[SubTaskResult]:
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
                return SubTaskResult(task_id=task.id, sub_task_id=0, success=True, result="No tools called")

            # 2. Execute Tools Parallel
            results = await asyncio.gather(*[
                self._execute_tool(tc, task.id, query_id) for tc in tool_calls
            ], return_exceptions=True)

            return SubTaskResult(task_id=task.id, sub_task_id=0, success=True, result=results)

        except Exception as e:
            logger.error(f"Task {task.id} failed: {e}")
            return SubTaskResult(task_id=task.id, sub_task_id=0, success=False, error=str(e))

    async def _resolve_tools(self, task: PlannedTask) -> List[ToolCall]:
        """Ask LLM which tools to call for the subtasks."""
        
        subtasks_str = "\\n".join([f"- {st.description}" for st in task.sub_tasks])
        tools_schema = self.registry.get_tools_schema() # Assumed method on registry

        # System message: context and instructions
        system_prompt = f"""You are an expert agent execution engine.
        
        Available Tools:
        {tools_schema}
        
        Return a JSON list of tool calls to satisfy the given subtasks.
        """
        
        from pydantic import BaseModel
        
        # Pydantic schema for list of tool calls
        class ToolCallList(BaseModel):
            calls: List[ToolCall]
        
        system_prompt += f"\\n\\nReturn JSON matching: {ToolCallList.model_json_schema()}"

        # User message: the actual task and subtasks to process
        user_prompt = f"""Task: {task.description}
        
        Subtasks to complete:
        {subtasks_str}
        
        Decide which tools to call to satisfy these subtasks."""

        response = await self.client.chat_completion(
            messages=[
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=user_prompt)
            ],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        
        content = response.content
        # Basic cleanup
        if content.startswith('```json'): content = content[7:-3]
        
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
                query_id=query_id
            )
            
            return {"tool": call.tool, "args": call.args, "output": result}
        except Exception as e:
            logger.error(f"Tool execution {call.tool} failed: {e}")
            return {"tool": call.tool, "error": str(e)}
