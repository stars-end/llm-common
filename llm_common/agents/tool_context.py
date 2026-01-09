import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any

from llm_common.agents.context_pointers import (
    ContextPointer,
    ContextRelevanceSelector,
    FileContextPointerStore,
    format_selected_contexts,
)
from llm_common.core import LLMClient

logger = logging.getLogger(__name__)


class ToolContextManager:
    """
    Manages filesystem persistence of tool executions.
    This enables 'Glass Box' observability by saving inputs/outputs to disk.
    """

    def __init__(self, base_dir: Path, pointer_store: FileContextPointerStore | None = None):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._sources: dict[str, list[dict]] = {}  # query_id -> sources
        self._pointer_store = pointer_store or FileContextPointerStore(
            base_dir=self.base_dir / "_pointers"
        )

    @property
    def pointer_store(self) -> FileContextPointerStore:
        return self._pointer_store

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
                    self._sources[query_id].append(
                        {
                            "tool": tool_name,
                            "url": result.get("url"),
                            "title": result.get("title", tool_name),
                        }
                    )
                elif "sources" in result:
                    self._sources[query_id].extend(result["sources"])

            # Persist a deterministic pointer (meta + result) for relevance selection.
            try:
                source_urls: list[str] = []
                if isinstance(result, dict):
                    if isinstance(result.get("source_urls"), list):
                        source_urls.extend([u for u in result["source_urls"] if isinstance(u, str)])
                    if isinstance(result.get("url"), str):
                        source_urls.append(result["url"])
                    if isinstance(result.get("sources"), list):
                        for item in result["sources"]:
                            if isinstance(item, dict) and isinstance(item.get("url"), str):
                                source_urls.append(item["url"])

                await self._pointer_store.save(
                    query_id=query_id,
                    task_id=task_id,
                    tool_name=tool_name,
                    args=args,
                    result=result,
                    source_urls=source_urls or None,
                )
            except Exception as e:
                logger.error(f"Failed to save context pointer: {e}")

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

    def list_pointers(self, query_id: str) -> list[ContextPointer]:
        return self._pointer_store.list(query_id=query_id)

    async def select_relevant_contexts(
        self,
        *,
        query_id: str,
        query: str,
        client: LLMClient,
        model: str | None = None,
        max_selected: int | None = None,
        max_chars: int = 20000,
    ) -> str:
        pointers = self.list_pointers(query_id)
        if not pointers:
            return ""

        selector = ContextRelevanceSelector(client=client, model=model, max_selected=max_selected)
        selected = await selector.select(query=query, pointers=pointers)
        if not selected:
            selected = pointers[-(max_selected or 6) :]
        return format_selected_contexts(
            pointers=selected, store=self._pointer_store, max_chars=max_chars
        )

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
