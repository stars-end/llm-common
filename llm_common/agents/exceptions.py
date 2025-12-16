"""Exceptions for E2E Agent."""

class AgentError(Exception):
    """Base class for agent errors."""
    def __init__(self, message: str, type: str = "unknown", severity: str = "medium", details: dict = None):
        super().__init__(message)
        self.type = type
        self.severity = severity
        self.details = details or {}

class NavigationError(AgentError):
    """Raised when navigation fails."""
    def __init__(self, message: str):
        super().__init__(message, type="navigation", severity="high")

class ElementNotFoundError(AgentError):
    """Raised when element interaction fails."""
    def __init__(self, message: str):
        super().__init__(message, type="element_not_found", severity="high")
