from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AdvisorRequest(BaseModel):
    """Request to the advisor."""
    user_query: str = Field(..., description="The user's query.")
    context: dict[str, Any] | None = Field(None, description="Optional context for the query.")


class AdvisorResponse(BaseModel):
    """Response from the advisor."""
    content: str = Field(..., description="The advisor's response.")
    sources: list[str] = Field(default_factory=list, description="List of sources used to generate the response.")
