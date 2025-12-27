"""Tool abstractions for the agent framework.

This module provides:
- BaseTool: Abstract base class for tools
- ToolMetadata: Describes a tool's capabilities
- ToolParameter: Describes a tool parameter
- ToolResult: Wraps tool execution results
- ToolRegistry: Manages registered tools
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from llm_common.agents.provenance import EvidenceEnvelope


@dataclass
class ToolParameter:
    """Describes a parameter for a tool."""

    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None


@dataclass
class ToolMetadata:
    """Describes a tool's capabilities and interface."""

    name: str
    description: str
    parameters: list[ToolParameter] = field(default_factory=list)

    def to_schema(self) -> dict[str, Any]:
        """Convert to JSON schema format for LLM function calling."""
        properties = {}
        required = []

        for param in self.parameters:
            properties[param.name] = {"type": param.type, "description": param.description}
            if param.required:
                required.append(param.name)

        return {"type": "object", "properties": properties, "required": required}


@dataclass
class ToolResult:
    """Wraps the result of a tool execution.

    Attributes:
        success: Whether the tool execution succeeded
        data: The result data from the tool
        source_urls: URLs that sourced this data (for provenance/citations)
        evidence: Optional evidence envelopes (Dexter-style provenance)
        error: Error message if execution failed
    """

    success: bool
    data: Any = None
    source_urls: list[str] = field(default_factory=list)
    evidence: list[EvidenceEnvelope] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "data": self.data,
            "source_urls": self.source_urls,
            "evidence": [e.model_dump() for e in self.evidence],
            "error": self.error,
        }


class BaseTool(ABC):
    """Abstract base class for tools that can be registered with ToolRegistry."""

    @property
    @abstractmethod
    def metadata(self) -> ToolMetadata:
        """Return tool metadata describing capabilities and parameters."""
        pass

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given parameters."""
        pass


class ToolRegistry:
    """Registry for managing tools available to the agent."""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool with the registry."""
        self._tools[tool.metadata.name] = tool

    def unregister(self, name: str) -> None:
        """Unregister a tool by name."""
        if name in self._tools:
            del self._tools[name]

    def get(self, name: str) -> BaseTool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[dict[str, str]]:
        """List all registered tools with name and description."""
        return [
            {"name": t.metadata.name, "description": t.metadata.description}
            for t in self._tools.values()
        ]

    def get_tools_schema(self) -> str:
        """Get JSON schema for all registered tools."""
        import json

        schemas = []
        for tool in self._tools.values():
            meta = tool.metadata
            schemas.append(
                {"name": meta.name, "description": meta.description, "parameters": meta.to_schema()}
            )
        return json.dumps(schemas, indent=2)

    async def execute(self, tool_name: str, **kwargs) -> ToolResult:
        """Execute a tool by name with given arguments."""
        tool = self._tools.get(tool_name)
        if not tool:
            return ToolResult(success=False, error=f"Tool '{tool_name}' not found")

        try:
            return await tool.execute(**kwargs)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


__all__ = [
    "BaseTool",
    "ToolMetadata",
    "ToolParameter",
    "ToolResult",
    "ToolRegistry",
]
