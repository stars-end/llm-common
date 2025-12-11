import inspect
from typing import Any, Callable, Dict, List, Optional, get_type_hints
import json
from enum import Enum

from pydantic import BaseModel

class ToolContextManager:
    """Manages tools available to an agent, including schema generation and execution."""

    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._schemas: Dict[str, Dict[str, Any]] = {}

    def register_tool(self, func: Callable, name: Optional[str] = None, description: Optional[str] = None) -> None:
        """Register a python function as a tool."""
        tool_name = name or func.__name__
        tool_desc = description or func.__doc__ or "No description provided."
        
        self._tools[tool_name] = func
        self._schemas[tool_name] = self._generate_schema(func, tool_name, tool_desc)

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Get list of tool schemas in OpenAI format."""
        return list(self._schemas.values())

    def execute_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool by name with arguments."""
        if name not in self._tools:
            raise ValueError(f"Tool '{name}' not found.")
        
        func = self._tools[name]
        try:
            return func(**arguments)
        except Exception as e:
            raise RuntimeError(f"Error executing tool '{name}': {str(e)}")

    def _generate_schema(self, func: Callable, name: str, description: str) -> Dict[str, Any]:
        """Generate OpenAI function schema from python function signature."""
        type_hints = get_type_hints(func)
        signature = inspect.signature(func)
        parameters = {}
        required = []

        for param_name, param in signature.parameters.items():
            if param_name == 'self':
                continue
            
            param_type = type_hints.get(param_name, Any)
            param_schema = self._get_type_schema(param_type)
            
            # Add description if available (could be parsed from docstring in improved version)
            
            parameters[param_name] = param_schema
            
            if param.default == inspect.Parameter.empty:
                required.append(param_name)

        return {
            "type": "function",
            "function": {
                "name": name,
                "description": description.strip(),
                "parameters": {
                    "type": "object",
                    "properties": parameters,
                    "required": required,
                },
            },
        }

    def _get_type_schema(self, py_type: Any) -> Dict[str, Any]:
        """Map python types to JSON schema types."""
        if py_type == str:
            return {"type": "string"}
        elif py_type == int:
            return {"type": "integer"}
        elif py_type == float:
            return {"type": "number"}
        elif py_type == bool:
            return {"type": "boolean"}
        elif py_type == list or getattr(py_type, "__origin__", None) == list:
            return {"type": "array", "items": {"type": "string"}} # Simplified
        elif py_type == dict or getattr(py_type, "__origin__", None) == dict:
            return {"type": "object"}
        elif isinstance(py_type, type) and issubclass(py_type, Enum):
            return {"type": "string", "enum": [e.value for e in py_type]}
        else:
            return {"type": "string"} # Default fallback
