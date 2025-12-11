from typing import Any, Dict, List
import asyncio
import logging

from .planner import TaskPlan, PlanStep
from .tool_context import ToolContextManager

logger = logging.getLogger(__name__)

class TaskExecutor:
    """Executes a TaskPlan using provided tools."""

    def __init__(self, tool_context: ToolContextManager):
        self.ctx = tool_context
        self.step_results: Dict[str, Any] = {}

    async def execute_plan(self, plan: TaskPlan) -> Dict[str, Any]:
        """Execute a plan sequentially (respecting dependencies implicitly by order for now)."""
        logger.info(f"Starting execution of plan: {plan.reasoning}")
        
        for step in plan.steps:
            await self._execute_step(step)
            
        return self.step_results

    async def _execute_step(self, step: PlanStep):
        """Execute a single step."""
        logger.info(f"Executing step {step.id}: {step.description}")
        
        try:
            if step.tool_name:
                # Resolve arguments potentially? (For now assumes direct values)
                args = step.tool_arguments or {}
                
                # Check if tool exists
                result = self.ctx.execute_tool(step.tool_name, args)
                if asyncio.iscoroutine(result):
                    result = await result
                
                self.step_results[step.id] = result
                logger.info(f"Step {step.id} completed. Result: {str(result)[:100]}...")
            else:
                # Just a reasoning step or manual action
                self.step_results[step.id] = "Completed (No tool)"
                
        except Exception as e:
            logger.error(f"Step {step.id} failed: {e}")
            self.step_results[step.id] = f"Error: {str(e)}"
            # In a real agent, we might want to halt or replan here
            raise e
