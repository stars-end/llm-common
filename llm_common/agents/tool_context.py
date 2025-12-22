import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List

from llm_common.agents import models as agent_models
from llm_common.retrieval import base as retrieval_base

logger = logging.getLogger(__name__)


class ToolContextManager:
    """
    Manages filesystem persistence of tool executions.
    This enables 'Glass Box' observability by saving inputs/outputs to disk.
    """

    def __init__(self, base_dir: Path, retriever: retrieval_base.RetrievalBackend | None = None):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._retriever = retriever
        self._tool_map: Dict[str, agent_models.Tool] = {}

    def register_tool(self, tool: agent_models.Tool) -> None:
        """Registers a tool with the context manager."""
        self._tool_map[tool.name] = tool

    def get_tool_description(self, tool_name: str) -> str:
        """Returns the description for a given tool."""
        if tool_name not in self._tool_map:
            raise ValueError(f"Tool '{tool_name}' not found.")
        return self._tool_map[tool_name].description

    async def save_context(
        self,
        tool_name: str,
        args: dict[str, Any],
        result: Any,
        task_id: str,
        query_id: str,
    ):
        """Save tool execution context to a JSON file."""
        try:
            timestamp = int(time.time() * 1000)
            file_name = f"{timestamp}_{task_id}_{tool_name}.json"

            # Create session/query directory
            query_dir = self.base_dir / query_id
            query_dir.mkdir(parents=True, exist_ok=True)

            file_path = query_dir / file_name

            data = {
                "tool": tool_name,
                "args": args,
                "result": result,
                "task_id": task_id,
                "query_id": query_id,
                "timestamp": timestamp,
            }

            # Handle non-serializable content nicely if needed
            with open(file_path, "w") as f:
                json.dump(data, f, default=str, indent=2)

            logger.debug(f"Saved context to {file_path}")

        except Exception as e:
            logger.error(f"Failed to save context: {e}")

    def load_relevant_contexts(self, query_id: str) -> str:
        """Load all context files for a query and return as a string blob."""
        query_dir = self.base_dir / query_id
        if not query_dir.exists():
            return ""

        contexts = []
        for f in sorted(query_dir.glob("*.json")):
            try:
                with open(f) as fd:
                    data = json.load(fd)
                    contexts.append(f"Tool: {data['tool']}\\nResult: {data['result']}")
            except Exception:
                pass

        return "\\n\\n".join(contexts)

    async def select_relevant_contexts(
        self, query: str, tool_name: str, k: int
    ) -> List[str]:
        """Selects the k most relevant contexts for a given query and tool."""
        if not self._retriever:
            return []
        
        documents = await self._retriever.retrieve(
            query=query, filters={"tool": tool_name}, k=k
        )
        return [doc.content for doc in documents]
