import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ToolContextManager:
    """
    Manages filesystem persistence of tool executions.
    This enables 'Glass Box' observability by saving inputs/outputs to disk.
    """

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def save_context(
        self, tool_name: str, args: dict[str, Any], result: Any, task_id: str, query_id: str
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
