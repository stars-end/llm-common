from typing import List, Optional
from pydantic import BaseModel, Field
import json
from llm_common.core import LLMClient

class PlanStep(BaseModel):
    """A single step in a task plan."""
    id: str
    description: str
    tool_name: Optional[str] = None
    tool_arguments: Optional[dict] = None
    dependencies: List[str] = Field(default_factory=list)

class TaskPlan(BaseModel):
    """A complete plan for achieving a goal."""
    steps: List[PlanStep]
    reasoning: str

class TaskPlanner:
    """Generates execution plans for complex tasks using an LLM."""

    def __init__(self, llm_client: LLMClient, model_name: str = "claude-3-5-sonnet"):
        self.llm = llm_client
        self.model_name = model_name

    async def create_plan(self, goal: str, available_tools: List[dict], context: str = "") -> TaskPlan:
        """Generate a plan to achieve the goal using available tools."""
        
        system_prompt = """You are an expert task planner. Your goal is to break down a user request into a sequence of logical steps.
        
        Available tools are provided in the schema.
        
        Return a JSON object with the following structure:
        {
            "reasoning": "Explanation of your plan...",
            "steps": [
                {
                    "id": "step_1",
                    "description": "Description of what to do",
                    "tool_name": "exact_tool_name_or_null",
                    "tool_arguments": { "arg": "value" },
                    "dependencies": []
                }
            ]
        }
        """

        user_prompt = f"""Goal: {goal}
        
        Context: {context}
        
        Available Tools: {json.dumps(available_tools, indent=2)}
        
        Generate a plan."""

        response = await self.llm.generate(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.0
        )

        try:
            plan_dict = json.loads(response.content)
            return TaskPlan(**plan_dict)
        except Exception as e:
            raise ValueError(f"Failed to parse plan from LLM: {str(e)}")
