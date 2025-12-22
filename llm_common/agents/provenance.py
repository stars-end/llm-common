from dataclasses import dataclass, field
from typing import List

@dataclass
class Evidence:
    """Represents a piece of evidence with its source and content."""
    url: str
    content: str

@dataclass
class EvidenceEnvelope:
    """A container for a collection of evidence."""
    evidence: List[Evidence] = field(default_factory=list)


@dataclass
class ValidatedCitations:
    """Holds validated and invalidated citations."""
    valid: List[str] = field(default_factory=list)
    invalid: List[str] = field(default_factory=list)


def validate_citations(
    citations: List[str], evidence: List[EvidenceEnvelope]
) -> ValidatedCitations:
    """
    Validates a list of citation URLs against a list of evidence.

    Args:
        citations: A list of citation URLs to validate.
        evidence: A list of EvidenceEnvelope objects to check against.

    Returns:
        A ValidatedCitations object containing lists of valid and invalid URLs.
    """
    if not evidence:
        return ValidatedCitations(valid=[], invalid=citations)

    evidence_urls = {
        e.url for envelope in evidence for e in envelope.evidence
    }

    validated = ValidatedCitations()
    for citation_url in citations:
        if citation_url in evidence_urls:
            validated.valid.append(citation_url)
        else:
            validated.invalid.append(citation_url)

    return validated
