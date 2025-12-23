"""
Provenance tracking for agent tool results.

This module provides data structures for tracking evidence provenance
throughout the agent execution pipeline, enabling citation validation
and audit trails.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import json
import uuid


@dataclass
class Evidence:
    """
    Represents a piece of evidence with full provenance tracking.
    
    Implements the v14 spec with id, kind, label for classification
    and derived_from for evidence chains.
    """
    # Unique identifier for this piece of evidence
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    
    # Classification: "url", "internal", "legislation", "derived", "api"
    kind: str = "url"
    
    # Human-readable label for display
    label: str = ""
    
    # Source URL if applicable
    url: str = ""
    
    # Full content or relevant excerpt
    content: str = ""
    
    # Short excerpt for display
    excerpt: Optional[str] = None
    
    # Additional metadata (timestamps, confidence, etc.)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # IDs of source evidence this was derived from
    derived_from: List[str] = field(default_factory=list)
    
    # Timestamp when evidence was collected
    collected_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "kind": self.kind,
            "label": self.label,
            "url": self.url,
            "content": self.content,
            "excerpt": self.excerpt,
            "metadata": self.metadata,
            "derived_from": self.derived_from,
            "collected_at": self.collected_at,
        }


@dataclass
class EvidenceEnvelope:
    """
    A container for a collection of evidence with tracking metadata.
    
    This is the primary provenance container passed through the agent pipeline.
    Each tool execution should produce an EvidenceEnvelope.
    """
    # Unique identifier for this envelope
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    
    # Collection of evidence items
    evidence: List[Evidence] = field(default_factory=list)
    
    # Name of the tool that produced this evidence
    source_tool: str = ""
    
    # Query that triggered the evidence collection
    source_query: str = ""
    
    # When envelope was created
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def get_by_id(self, evidence_id: str) -> Optional[Evidence]:
        """Get evidence by ID."""
        return next((e for e in self.evidence if e.id == evidence_id), None)
    
    def get_urls(self) -> List[str]:
        """Get all URLs in this envelope."""
        return [e.url for e in self.evidence if e.url]
    
    def get_ids(self) -> List[str]:
        """Get all evidence IDs in this envelope."""
        return [e.id for e in self.evidence]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "evidence": [e.to_dict() for e in self.evidence],
            "source_tool": self.source_tool,
            "source_query": self.source_query,
            "created_at": self.created_at,
        }


@dataclass
class ValidatedCitations:
    """Holds validated and invalidated citations with details."""
    valid: List[str] = field(default_factory=list)
    invalid: List[str] = field(default_factory=list)
    # Map from citation to evidence ID
    citation_to_evidence: Dict[str, str] = field(default_factory=dict)


def validate_citations(
    citations: List[str], 
    evidence: List[EvidenceEnvelope],
    use_ids: bool = False,
) -> ValidatedCitations:
    """
    Validates a list of citations against collected evidence.

    Args:
        citations: List of citation strings (URLs or evidence IDs)
        evidence: List of EvidenceEnvelope objects to check against
        use_ids: If True, match by evidence ID instead of URL

    Returns:
        ValidatedCitations with valid/invalid lists and ID mappings
    """
    if not evidence:
        return ValidatedCitations(valid=[], invalid=citations)

    validated = ValidatedCitations()
    
    if use_ids:
        # ID-based validation
        evidence_ids = {
            e.id: e for envelope in evidence for e in envelope.evidence
        }
        for citation in citations:
            if citation in evidence_ids:
                validated.valid.append(citation)
                validated.citation_to_evidence[citation] = citation
            else:
                validated.invalid.append(citation)
    else:
        # URL-based validation (legacy compatibility)
        url_to_id = {
            e.url: e.id for envelope in evidence for e in envelope.evidence if e.url
        }
        for citation_url in citations:
            if citation_url in url_to_id:
                validated.valid.append(citation_url)
                validated.citation_to_evidence[citation_url] = url_to_id[citation_url]
            else:
                validated.invalid.append(citation_url)

    return validated


def format_tool_result(
    data: Any,
    source_urls: Optional[List[str]] = None,
    evidence: Optional[EvidenceEnvelope] = None,
) -> str:
    """
    Format tool result with provenance envelope.
    
    Implements Dexter's formatToolResult() pattern for consistent
    provenance handling across all tools.
    
    Args:
        data: The tool output payload
        source_urls: Optional list of source URLs
        evidence: Optional EvidenceEnvelope with full provenance
        
    Returns:
        JSON string containing data, sourceUrls, and optional evidence
    """
    result: Dict[str, Any] = {"data": data}
    
    if source_urls:
        result["sourceUrls"] = source_urls
    
    if evidence:
        result["evidence"] = evidence.to_dict()
        # Also include sourceUrls from evidence if not already set
        if not source_urls:
            result["sourceUrls"] = evidence.get_urls()
    
    return json.dumps(result, default=str)

