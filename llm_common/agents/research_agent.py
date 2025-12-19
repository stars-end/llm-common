import uuid
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from llm_common.core import LLMClient
from llm_common.web_search import WebSearchClient
from llm_common.agents.planner import TaskPlanner
from llm_common.agents.executor import AgenticExecutor
from llm_common.agents.tool_context import ToolContextManager

logger = logging.getLogger(__name__)

class ToolRegistry:
    """Simple internal registry for the ResearchAgent."""
    def __init__(self):
        self._tools = {}
        self._schemas = []

    def register(self, name: str, description: str, func: Any, schema: Dict[str, Any]):
        self._tools[name] = func
        self._schemas.append({
            "name": name,
            "description": description,
            "parameters": schema
        })

    def get_tools_schema(self) -> str:
        import json
        return json.dumps(self._schemas, indent=2)

    async def execute(self, tool_name: str, args: Dict[str, Any]) -> Any:
        if tool_name not in self._tools:
            raise ValueError(f"Tool {tool_name} not found")
        return await self._tools[tool_name](**args)

class ResearchAgent:
    """
    Agent specialized for research tasks.
    Uses TaskPlanner to break down research questions and AgenticExecutor to gather data via web search.
    """

    def __init__(self, llm_client: LLMClient, search_client: WebSearchClient, work_dir: str = "/tmp/research_agent"):
        self.llm = llm_client
        self.search = search_client
        self.work_dir = Path(work_dir)
        
        # Initialize sub-components
        self.planner = TaskPlanner(self.llm)
        self.context_manager = ToolContextManager(self.work_dir)
        
        # Setup Tool Registry
        self.registry = ToolRegistry()
        self._register_tools()
        
        # Executor
        self.executor = AgenticExecutor(self.llm, self.registry, self.context_manager)

    def _register_tools(self):
        """Register default research tools."""
        
        async def search_tool(query: str, count: int = 5) -> Dict[str, Any]:
            """Perform a web search."""
            try:
                # Use "1y" recency for legislation research typically, or let agent decide?
                # For generally verifying statements, no recency is safer unless specified.
                response = await self.search.search(query, count=count)
                return response.model_dump()
            except Exception as e:
                return {"error": str(e)}

        self.registry.register(
            name="web_search",
            description="Search the web for information. Use this to find facts, news, legislation text, and analysis.",
            func=search_tool,
            schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "count": {"type": "integer", "description": "Number of results (default 5)"}
                },
                "required": ["query"]
            }
        )

    async def run(self, bill_id: str, bill_text: str, jurisdiction: str) -> Dict[str, Any]:
        """
        Run the research agent workflow.
        
        Args:
            bill_id: Identifier for the bill/topic
            bill_text: Context/text of the bill
            jurisdiction: Target jurisdiction
            
        Returns:
            Dict containing collected data and summary
        """
        run_id = str(uuid.uuid4())
        
        # 1. Plan
        # We frame the query for the planner
        query = f"Research the cost of living impacts and opposition arguments for bill {bill_id} in {jurisdiction}."
        context = {
            "bill_id": bill_id,
            "jurisdiction": jurisdiction,
            "text_preview": bill_text[:500] if bill_text else ""
        }
        
        # Pass available tools to planner so it knows what it can do
        # The schema expected by planner optional args is List[dict] with name/desc
        available_tools_summary = [
            {"name": t["name"], "description": t["description"]} 
            for t in self.registry._schemas
        ]
        
        logger.info(f"Generating research plan for {bill_id}...")
        plan = await self.planner.plan(query, context=context, available_tools=available_tools_summary)
        
        if not plan.tasks:
            logger.warning("Planner returned no tasks.")
            return {"error": "Planning failed", "collected_data": []}
            
        # 2. Execute
        logger.info(f"Executing plan with {len(plan.tasks)} tasks...")
        results = await self.executor.execute_plan(plan, run_id)
        
        # 3. Aggregate
        # Collect all successful tool outputs
        collected_data = []
        for res in results:
            if not res.success:
                continue
            
            # Result is typically a list of dicts from executor._execute_tool calls in parallel
            # SubTaskResult.result depends on implementation. 
            # execute_task returns SubTaskResult(result=[...])
            if isinstance(res.result, list):
                collected_data.extend(res.result)
            else:
                collected_data.append(res.result)
                
        return {
            "plan": plan.model_dump(),
            "collected_data": collected_data,
            "run_id": run_id,
            "status": "success"
        }
