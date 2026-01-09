"""
Provenance tracking for AI agent responses.

This module provides:
- Evidence: A single piece of evidence with full provenance
- EvidenceEnvelope: A container for multiple pieces of evidence
- validate_citations: Verify citation IDs in text against envelope

Feature-Key: affordabot-dmzy.4
"""

import re
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Evidence(BaseModel):
    """Represents a piece of evidence with full provenance.

    Attributes:
        id: Unique identifier (UUID)
        kind: Type of evidence (url, internal, legislation, derived)
        label: Human-readable label
        url: Source URL if applicable
        content: Full content of the evidence
        excerpt: Relevant excerpt from content
        metadata: Additional metadata
        derived_from: IDs of source evidence this was derived from
        tool_name: Optional tool name that produced this evidence
        tool_args: Optional tool arguments (when applicable)
        retrieved_at: ISO timestamp of retrieval
        content_hash: Optional hash for integrity checking
        internal_ref: Optional internal reference (e.g., account/session ID)
        confidence: Optional confidence score (0.0-1.0)
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    kind: str = Field(default="url", description="url | internal | legislation | derived")
    label: str = ""
    url: str = ""
    content: str = ""
    excerpt: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    derived_from: list[str] = Field(default_factory=list)
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    retrieved_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    content_hash: str | None = None
    internal_ref: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class EvidenceEnvelope(BaseModel):
    """A container for a collection of evidence with tracking.

    Attributes:
        id: Unique identifier for this envelope
        evidence: List of Evidence objects
        created_at: ISO timestamp of creation
        source_tool: Name of the tool that created this envelope
        source_query: Optional query/input that produced this envelope
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    evidence: list[Evidence] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    source_tool: str = ""
    source_query: str | None = None

    def get_by_id(self, evidence_id: str) -> Evidence | None:
        """Get evidence by its ID."""
        return next((item for item in self.evidence if item.id == evidence_id), None)

    def get_urls(self) -> list[str]:
        """Get all URLs in this envelope."""
        return [item.url for item in self.evidence if item.url]

    def add(self, evidence: Evidence) -> None:
        """Add evidence to the envelope."""
        self.evidence.append(evidence)

    def merge(self, other: "EvidenceEnvelope") -> None:
        """Merge another envelope into this one."""
        self.evidence.extend(other.evidence)


def validate_citations(answer: str, envelope: EvidenceEnvelope) -> tuple[bool, list[str]]:
    """Check if all citation IDs in the answer exist in the envelope.

    Looks for UUID patterns in square brackets like [a1b2c3d4-e5f6-...].

    Args:
        answer: The answer text to check
        envelope: The EvidenceEnvelope to validate against

    Returns:
        Tuple of (is_valid, missing_ids)
    """
    # Match UUIDs in square brackets
    uuid_pattern = r"\[([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})\]"
    cited_ids = re.findall(uuid_pattern, answer, re.IGNORECASE)

    missing = [cid for cid in cited_ids if not envelope.get_by_id(cid)]
    return len(missing) == 0, missing


def format_tool_result(
    tool_name: str,
    url: str | None = None,
    content: str = "",
    metadata: dict | None = None,
) -> Evidence:
    """Create an Evidence object from a tool result.

    Helper function for tools to create properly formatted evidence.

    Args:
        tool_name: Name of the tool
        url: Optional source URL
        content: Content from the tool
        metadata: Optional additional metadata

    Returns:
        Evidence object
    """
    return Evidence(
        kind="url" if url else "internal",
        label=tool_name,
        url=url or "",
        content=content,
        metadata=metadata or {},
        tool_name=tool_name,
    )
