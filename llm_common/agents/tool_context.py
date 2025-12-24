import hashlib
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
        self._sources: dict[str, list[dict]] = {}  # query_id -> sources

    def hash_query(self, query: str) -> str:
        """Generate a stable, short hash for a query string.
        
        Used for deduplication and context file naming.
        Returns a 12-character hex digest.
        """
        return hashlib.sha256(query.encode()).hexdigest()[:12]

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

            # Track sources for this query
            if query_id not in self._sources:
                self._sources[query_id] = []
            
            # Extract source info if available in result
            if isinstance(result, dict):
                if "url" in result:
                    self._sources[query_id].append({
                        "tool": tool_name,
                        "url": result.get("url"),
                        "title": result.get("title", tool_name),
                    })
                elif "sources" in result:
                    self._sources[query_id].extend(result["sources"])

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

    def get_all_sources(self, query_id: str) -> list[dict]:
        """Get all sources collected during query execution.
        
        Returns a list of source dictionaries with tool, url, and title.
        Used by run_stream() to yield sources at the end of execution.
        """
        return self._sources.get(query_id, [])

    def clear_sources(self, query_id: str) -> None:
        """Clear sources for a query (used after yielding)."""
        if query_id in self._sources:
            del self._sources[query_id]

