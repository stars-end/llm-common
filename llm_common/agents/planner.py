import logging
from typing import List, Optional, Any
from .schemas import ExecutionPlan, PlannedTask
from llm_common.core import LLMClient

logger = logging.getLogger(__name__)

class TaskPlanner:
    """
    Port of Dexter's TaskPlanner.
    Generates structured execution plans with tasks and subtasks.
    """

    def __init__(self, client: LLMClient):
        self.client = client

    async def plan(self, query: str, context: Optional[dict] = None, available_tools: Optional[List[dict]] = None) -> ExecutionPlan:
        """
        Generate a hierarchical execution plan from a user query.
        """
        try:
            # Construct System Prompt (Ported from Dexter)
            tool_desc = ""
            if available_tools:
                tool_desc = "\\n".join([f"- {t.get('name')}: {t.get('description')}" for t in available_tools])

            system_prompt = f"""You are an expert task planner for a financial research assistant.
            
            Available Tools:
            {tool_desc}

            Your goal is to break down the user's query into a LIST of high-level tasks.
            Each task must have specific SUBTASKS that describe exactly what data to gather.
            
            Rules:
            1. Create separate tasks for parallelizable work (e.g. researching different companies).
            2. Be extremely specific in subtask descriptions (mention tickers, years, metric names).
            3. Do not try to answer the question yet, just PLAN how to get the data.
            """

            user_msg = f"User Query: {query}\\n"
            if context:
                user_msg += f"Context: {context}\\n"
            
            user_msg += "\\nCreate an execution plan."

            # Use Instructor via the client (assuming client exposes access or we wrap it)
            # Since LLMClient might not strictly expose instructor yet, we use the raw chat_completion if needed,
            # but ideally we use a method that supports response_model.
            # Check LLMClient capability. If not available, we use standard JSON mode.
            
            # Implementation Note: `llm-common` v1 might not have instructor baked in `LLMClient`.
            # We will use the `response_format={"type": "json_object"}` and Pydantic validation for now,
            # or `instructor.patch()` if we can access the raw client.
            # For stability in this port, we'll assume JSON mode + prompt engineering.

            system_prompt += f"\\n\\nReturn JSON matching this schema:\\n{ExecutionPlan.model_json_schema()}"

            response = await self.client.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg}
                ],
                response_format={"type": "json_object"},
                temperature=0.0
            )

            content = response.content
            if hasattr(content, 'strip'):
                content = content.strip()
                if content.startswith('```json'):
                    content = content[7:-3]
            
            return ExecutionPlan.model_validate_json(content)

        except Exception as e:
            logger.error(f"Planning failed: {e}")
            # Return empty plan or re-raise
            return ExecutionPlan(tasks=[])
