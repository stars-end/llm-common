from __future__ import annotations

from typing import Any, Dict, List, Protocol

from llm_common.agents import models as agent_models


class AgentCallbacks(Protocol):
    """Protocol for agent callbacks."""

    def on_agent_start(self, name: str, query: str) -> None:
        """Called when the agent starts."""
        pass

    def on_agent_finish(self, name: str, output: agent_models.AgentOutput) -> None:
        """Called when the agent finishes."""
        pass

    def on_tool_start(self, tool_name: str, args: Dict[str, Any]) -> None:
        """Called when a tool starts."""
        pass

    def on_tool_finish(
        self,
        tool_name: str,
        output: Any,
        task_id: str | None = None,
        query_id: str | None = None,
    ) -> None:
        """Called when a tool finishes."""
        pass

    def on_thought_start(self) -> None:
        """Called when the agent starts thinking."""
        pass

    def on_thought_finish(self, thought: str) -> None:
        """Called when the agent finishes thinking."""
        pass

    def on_planner_start(self, components: List[str]) -> None:
        """Called when the planner starts."""
        pass

    def on_planner_finish(self, plan: agent_models.Plan) -> None:
        """Called when the planner finishes."""
        pass

    def on_synthesizer_start(self) -> None:
        """Called when the synthesizer starts."""
        pass

    def on_synthesizer_finish(self, response: str) -> None:
        """Called when the synthesizer finishes."""
        pass
