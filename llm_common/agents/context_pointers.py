import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from llm_common.core import LLMClient, LLMMessage


def _stable_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_pointer_id(*, tool_name: str, args: dict, query_id: str, task_id: str | None) -> str:
    """Computes a deterministic ID for a context pointer."""
    payload = {
        "tool_name": tool_name,
        "args": args,
        "query_id": query_id,
        "task_id": task_id,
    }
    digest = hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()
    return digest[:12]


def deterministic_summary(*, tool_name: str, args: dict) -> str:
    """Creates a deterministic, human-readable summary for a tool call."""
    keys = ["ticker", "query", "q", "symbol", "cusip", "isin", "period", "limit", "count", "url"]
    parts: list[str] = [tool_name]
    for key in keys:
        if key in args and args[key] is not None:
            parts.append(f"{key}={args[key]}")
    if len(parts) == 1 and args:
        for key in sorted(args.keys())[:3]:
            value = args[key]
            if value is not None:
                parts.append(f"{key}={value}")
    return " ".join(parts)


class ContextPointer(BaseModel):
    """A pointer to a cached result from a tool execution."""

    pointer_id: str = Field(..., description="Unique ID for this pointer.")
    query_id: str = Field(..., description="ID of the query this pointer belongs to.")
    task_id: str | None = Field(default=None, description="ID of the task, if any.")
    tool_name: str
    args: dict = Field(default_factory=dict)
    created_at: str
    summary: str
    result_path: str
    source_urls: list[str] = Field(default_factory=list)


class FileContextPointerStore:
    """Stores and retrieves context pointers and their results on the local filesystem."""

    def __init__(self, base_dir: Path | None = None):
        """
        Initializes the store.

        Args:
            base_dir: The base directory for storage. Defaults to the value of the
                      LLM_COMMON_POINTER_STORE_DIR environment variable or
                      '.llm-common/context'.
        """
        base = base_dir or Path(os.getenv("LLM_COMMON_POINTER_STORE_DIR", ".llm-common/context"))
        self._base_dir = base

    async def save(
        self,
        *,
        query_id: str,
        task_id: str | None,
        tool_name: str,
        args: dict,
        result: Any,
        source_urls: list[str] | None = None,
    ) -> ContextPointer:
        """
        Saves a tool execution result and its metadata to the store.

        Args:
            query_id: The ID of the current query.
            task_id: The ID of the current task, if any.
            tool_name: The name of the tool that was executed.
            args: The arguments passed to the tool.
            result: The JSON-serializable result from the tool.
            source_urls: A list of source URLs associated with the result, if any.

        Returns:
            The created ContextPointer.
        """
        pointer_id = compute_pointer_id(
            tool_name=tool_name, args=args, query_id=query_id, task_id=task_id
        )
        created_at = datetime.now(UTC).isoformat()
        summary = deterministic_summary(tool_name=tool_name, args=args)

        query_dir = self._base_dir / query_id
        query_dir.mkdir(parents=True, exist_ok=True)

        meta_path = query_dir / f"{pointer_id}.meta.json"
        result_path = query_dir / f"{pointer_id}.result.json"

        pointer = ContextPointer(
            pointer_id=pointer_id,
            query_id=query_id,
            task_id=task_id,
            tool_name=tool_name,
            args=args,
            created_at=created_at,
            summary=summary,
            result_path=str(result_path),
            source_urls=source_urls or [],
        )

        meta_path.write_text(pointer.model_dump_json(indent=2), encoding="utf-8")
        result_path.write_text(
            json.dumps(result, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        return pointer

    def list(self, *, query_id: str) -> list[ContextPointer]:
        """Lists all context pointers for a given query ID."""
        query_dir = self._base_dir / query_id
        if not query_dir.exists():
            return []
        pointers: list[ContextPointer] = []
        for meta_path in sorted(query_dir.glob("*.meta.json")):
            try:
                pointers.append(
                    ContextPointer.model_validate_json(meta_path.read_text(encoding="utf-8"))
                )
            except Exception:
                continue
        return pointers

    def load_result(self, *, pointer: ContextPointer) -> Any:
        """Loads the result associated with a context pointer."""
        return json.loads(Path(pointer.result_path).read_text(encoding="utf-8"))


class _PointerIdList(BaseModel):
    pointer_ids: list[str] = Field(default_factory=list)


def _env_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "t", "yes", "y", "on"}


class ContextRelevanceSelector:
    """Selects the most relevant context pointers for a given query."""

    def __init__(
        self,
        client: LLMClient,
        model: str | None = None,
        max_selected: int | None = None,
        fail_closed: bool | None = None,
    ):
        """
        Initializes the selector.

        Args:
            client: An LLMClient instance for making API calls.
            model: The model to use for selection. Defaults to environment variables.
            max_selected: The maximum number of pointers to select. Defaults to
                          environment variable or 6.
            fail_closed: If True, returns an empty list on failure. Defaults to
                         environment variable or True.
        """
        self._client = client
        default_model = os.getenv("LLM_COMMON_CONTEXT_SELECTION_MODEL") or os.getenv(
            "LLM_COMMON_TOOL_SELECTION_MODEL"
        )
        self._model = model or default_model
        self._max_selected = max_selected or int(
            os.getenv("LLM_COMMON_CONTEXT_SELECTION_MAX_POINTERS", "6")
        )
        self._fail_closed = (
            fail_closed
            if fail_closed is not None
            else _env_bool("LLM_COMMON_CONTEXT_SELECTION_FAIL_CLOSED", True)
        )

    async def select(self, *, query: str, pointers: list[ContextPointer]) -> list[ContextPointer]:
        """
        Selects the most relevant pointers from a list of candidates.

        Args:
            query: The user's query to determine relevance.
            pointers: A list of candidate ContextPointer objects.

        Returns:
            A filtered list of the most relevant pointers.
        """
        if not pointers:
            return []

        candidates = [{"pointer_id": p.pointer_id, "summary": p.summary} for p in pointers]

        system_prompt = (
            "You are a context selector.\n"
            "Pick only the most relevant context pointer IDs for the query.\n"
            "Return a JSON object matching the schema.\n\n"
            f"Return JSON matching: {json.dumps(_PointerIdList.model_json_schema(), indent=2)}"
        )
        user_prompt = (
            f"Query: {query}\n\nCandidates:\n"
            f"{json.dumps(candidates, indent=2, ensure_ascii=False)}\n"
        )

        try:
            response = await self._client.chat_completion(
                messages=[
                    LLMMessage(role="system", content=system_prompt),
                    LLMMessage(role="user", content=user_prompt),
                ],
                model=self._model,
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            parsed = _PointerIdList.model_validate_json(content)
            selected_ids = parsed.pointer_ids[: self._max_selected]
            selected_set = set(selected_ids)
            return [p for p in pointers if p.pointer_id in selected_set]
        except Exception:
            return [] if self._fail_closed else []


def format_selected_contexts(
    *,
    pointers: list[ContextPointer],
    store: FileContextPointerStore,
    max_chars: int = 20000,
) -> str:
    """
    Formats the results of selected context pointers into a single string.

    Args:
        pointers: The list of context pointers to format.
        store: The store to use for loading pointer results.
        max_chars: The maximum number of characters for the formatted string.

    Returns:
        A formatted string containing the context information, truncated if necessary.
    """
    chunks: list[str] = []
    for pointer in pointers:
        try:
            result = store.load_result(pointer=pointer)
        except Exception:
            continue
        chunks.append(
            f"### {pointer.tool_name} ({pointer.pointer_id})\n"
            f"{pointer.summary}\n\n"
            f"{json.dumps(result, indent=2, ensure_ascii=False, default=str)}\n"
        )

    blob = "\n\n".join(chunks)
    return blob[:max_chars] if len(blob) > max_chars else blob
