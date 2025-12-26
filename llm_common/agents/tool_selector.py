import json
import os
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from llm_common.agents.schemas import PlannedTask, ToolCall
from llm_common.core import LLMClient, LLMMessage


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def _parse_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class ToolSelectionConfig:
    model: str = "glm-4.5-air"
    fallback_model: str | None = None
    max_calls: int = 5
    timeout_s: int = 30
    temperature: float = 0.0
    fail_closed: bool = True

    @staticmethod
    def from_env() -> "ToolSelectionConfig":
        return ToolSelectionConfig(
            model=os.getenv("LLM_COMMON_TOOL_SELECTION_MODEL", "glm-4.5-air"),
            fallback_model=os.getenv("LLM_COMMON_TOOL_SELECTION_FALLBACK_MODEL") or None,
            max_calls=_parse_int(os.getenv("LLM_COMMON_TOOL_SELECTION_MAX_CALLS"), 5),
            timeout_s=_parse_int(os.getenv("LLM_COMMON_TOOL_SELECTION_TIMEOUT_S"), 30),
            fail_closed=_parse_bool(
                os.getenv("LLM_COMMON_TOOL_SELECTION_FAIL_CLOSED"), True
            ),
        )


class _ToolCallList(BaseModel):
    calls: list[ToolCall] = Field(default_factory=list)


class ToolSelector:
    def __init__(self, client: LLMClient, config: ToolSelectionConfig | None = None):
        self._client = client
        self._config = config or ToolSelectionConfig.from_env()

    async def select_tool_calls(
        self,
        *,
        task: PlannedTask,
        tool_registry: Any,
        query: str | None = None,
        context: dict | None = None,
    ) -> list[ToolCall]:
        tools_schema = tool_registry.get_tools_schema()
        subtasks_str = "\n".join([f"- {st.description}" for st in task.sub_tasks])

        system_prompt = (
            "You are an expert tool-routing engine.\n\n"
            "You MUST return a JSON object matching the provided schema.\n"
            "Select only the minimal necessary tools, and ensure args are valid.\n\n"
            f"Available Tools (JSON schema):\n{tools_schema}\n\n"
            f"Return JSON matching: {json.dumps(_ToolCallList.model_json_schema(), indent=2)}"
        )

        user_prompt = (
            f"Task: {task.description}\n\n"
            f"Subtasks:\n{subtasks_str}\n\n"
            f"User query (optional): {query or ''}\n\n"
            f"Context (optional): {json.dumps(context or {}, ensure_ascii=False)}\n"
        )

        async def _attempt(model: str) -> list[ToolCall]:
            response = await self._client.chat_completion(
                messages=[
                    LLMMessage(role="system", content=system_prompt),
                    LLMMessage(role="user", content=user_prompt),
                ],
                model=model,
                temperature=self._config.temperature,
                response_format={"type": "json_object"},
                timeout=self._config.timeout_s,
            )

            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            parsed = _ToolCallList.model_validate_json(content)
            return parsed.calls[: self._config.max_calls]

        try:
            return await _attempt(self._config.model)
        except Exception:
            if self._config.fallback_model:
                try:
                    return await _attempt(self._config.fallback_model)
                except Exception:
                    pass
            return []

