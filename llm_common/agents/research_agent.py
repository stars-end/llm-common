from typing import Any, Dict, List
import json
from .executor import TaskExecutor
from .planner import TaskPlanner, TaskPlan
from .tool_context import ToolContextManager
from llm_common.core import LLMClient
from llm_common.web_search import WebSearchClient

class ResearchAgent:
    """Agent specialized in legislative research."""

    def __init__(self, llm_client: LLMClient, search_client: WebSearchClient, model_name: str = "claude-3-5-sonnet"):
        self.llm = llm_client
        self.search_client = search_client
        self.model_name = model_name
        
        # Initialize agent components
        self.ctx = ToolContextManager()
        self._register_tools()
        
        self.planner = TaskPlanner(llm_client, model_name=model_name)
        self.executor = TaskExecutor(self.ctx)
        self.collected_data = []

    def _register_tools(self):
        """Register available tools for research."""
        self.ctx.register_tool(
            self._search_tool, 
            name="web_search", 
            description="Search the web for information. Use this to find news, official documents, and analysis."
        )

    async def _search_tool(self, query: str) -> str:
        """Execute a web search."""
        try:
            resp = await self.search_client.search(
                query=query, 
                count=5,
                domains=["*.gov", "*.edu", "*.org", "news.google.com"]
            )
            
            # Format results concisely for the agent
            self.collected_data.extend([r.model_dump() for r in resp.results])
            summary = [f"Source: {r.title} ({r.url})\nSnippet: {r.snippet}" for r in resp.results]
            return "\n\n".join(summary)
        except Exception as e:
            return f"Search failed: {str(e)}"

    async def run(self, bill_id: str, bill_text: str, jurisdiction: str) -> Dict[str, Any]:
        """Run the research process."""
        self.collected_data = [] # Reset for new run
        goal = f"Research the context, public sentiment, and official analysis for Bill {bill_id} in {jurisdiction}. Find supporting and opposing arguments."
        context = f"Bill Snippet: {bill_text[:1000]}..."
        
        # 1. Plan
        plan = await self.planner.create_plan(
            goal=goal, 
            available_tools=self.ctx.get_tool_schemas(), 
            context=context
        )
        
        # 2. Execute
        step_results = await self.executor.execute_plan(plan)
        
        # 3. Synthesize (Optional: could be another LLM call or just return raw results)
        # For now, return the plan and execution results
        return {
            "plan": plan.model_dump(),
            "results": step_results,
            "collected_data": self.collected_data,
            "summary": "Research completed." # Pending synthesis step
        }
