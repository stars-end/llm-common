"""Answer synthesis for the agent framework.

This module provides:
- AnswerSynthesizer: Generates grounded answers from collected data
- StructuredAnswer: Output schema for synthesized answers
"""

from dataclasses import dataclass, field
from typing import Any

try:
    from pydantic import BaseModel
except ImportError:
    BaseModel = None  # Pydantic is optional


@dataclass
class StructuredAnswer:
    """Represents a synthesized answer with optional citations.

    Attributes:
        content: The main answer text
        sources: List of source URLs used to generate the answer
        confidence: Optional confidence score (0.0-1.0)
        metadata: Optional additional metadata
    """

    content: str
    sources: list[str] = field(default_factory=list)
    confidence: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "content": self.content,
            "sources": self.sources,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


class AnswerSynthesizer:
    """Synthesizes grounded answers from collected tool outputs.

    This class follows the Dexter pattern of:
    1. Collecting tool outputs with provenance (source_urls)
    2. Optionally selecting relevant contexts
    3. Synthesizing an answer that cites sources

    Usage:
        synthesizer = AnswerSynthesizer(llm_client, require_sources=True)
        answer = await synthesizer.synthesize(
            query="What is Apple's revenue?",
            collected_data=[context1, context2],
            output_schema=FinancialAnalysisResponse  # Optional
        )
    """

    def __init__(
        self, llm_client: Any, require_sources: bool = True, format_rules: str | None = None
    ):
        """Initialize the synthesizer.

        Args:
            llm_client: The LLM client to use for synthesis
            require_sources: If True, enforce that answers include sources
            format_rules: Optional custom formatting instructions
        """
        self.llm_client = llm_client
        self.require_sources = require_sources
        self.format_rules = format_rules or self._default_format_rules()

    def _default_format_rules(self) -> str:
        """Default formatting rules for answer synthesis."""
        return """
When synthesizing your answer:
1. Lead with the KEY FINDING or direct answer
2. Include SPECIFIC NUMBERS with proper context (dates, units)
3. Use clear structure - separate key data points for readability
4. Provide brief analysis or insight when relevant

SOURCES SECTION (REQUIRED when data was collected):
At the END of your answer, include a "Sources:" section listing the data sources you used.
Format: "Sources:\n1. (description): URL"
Only include sources whose data you actually referenced.
"""

    async def synthesize(
        self,
        query: str,
        collected_data: list[dict[str, Any]],
        output_schema: type | None = None,
        conversation_context: str | None = None,
    ) -> StructuredAnswer:
        """Synthesize an answer from collected data.

        Args:
            query: The original user query
            collected_data: List of context dicts with 'data' and 'source_urls'
            output_schema: Optional Pydantic model for structured output
            conversation_context: Optional prior conversation for multi-turn

        Returns:
            StructuredAnswer with content and sources
        """
        # Extract all sources from collected data
        all_sources = []
        for ctx in collected_data:
            source_urls = ctx.get("source_urls", [])
            if isinstance(source_urls, list):
                all_sources.extend(source_urls)

        # Build the synthesis prompt
        prompt = self._build_synthesis_prompt(
            query=query, collected_data=collected_data, conversation_context=conversation_context
        )

        # Call LLM for synthesis
        try:
            if output_schema and BaseModel and issubclass(output_schema, BaseModel):
                # Structured output if Pydantic model provided
                response = await self._call_with_schema(prompt, output_schema)
                return StructuredAnswer(
                    content=str(response),
                    sources=all_sources,
                    metadata={"schema": output_schema.__name__},
                )
            else:
                # Plain text response
                response = await self._call_llm(prompt)
                return StructuredAnswer(content=response, sources=all_sources)
        except Exception as e:
            return StructuredAnswer(
                content=f"Error synthesizing answer: {str(e)}",
                sources=all_sources,
                metadata={"error": str(e)},
            )

    def _build_synthesis_prompt(
        self,
        query: str,
        collected_data: list[dict[str, Any]],
        conversation_context: str | None = None,
    ) -> str:
        """Build the synthesis prompt with collected data."""
        # Format collected data
        data_sections = []
        for i, ctx in enumerate(collected_data, 1):
            tool_name = ctx.get("tool_name", "unknown")
            data = ctx.get("data", ctx.get("result", {}))
            source_urls = ctx.get("source_urls", [])

            section = f"Data {i} from {tool_name}:\n{data}"
            if source_urls:
                section += f"\nSources: {', '.join(source_urls)}"
            data_sections.append(section)

        collected_text = "\n\n".join(data_sections) if data_sections else "No data collected."

        # Build full prompt
        prompt_parts = []

        if conversation_context:
            prompt_parts.append(f"Previous conversation:\n{conversation_context}\n---\n")

        prompt_parts.append(f'User query: "{query}"')
        prompt_parts.append(f"\nCollected data:\n{collected_text}")
        prompt_parts.append(f"\n{self.format_rules}")
        prompt_parts.append("\nProvide a comprehensive answer based on the data above.")

        return "\n".join(prompt_parts)

    async def _call_llm(self, prompt: str) -> str:
        """Call the LLM for plain text response."""
        # Use the llm_client's generate method
        if hasattr(self.llm_client, "generate"):
            response = await self.llm_client.generate(prompt)
            return response.content if hasattr(response, "content") else str(response)
        elif hasattr(self.llm_client, "complete"):
            response = await self.llm_client.complete(prompt)
            return str(response)
        else:
            raise ValueError("LLM client must have 'generate' or 'complete' method")

    async def _call_with_schema(self, prompt: str, schema: type) -> Any:
        """Call the LLM with structured output schema."""
        if hasattr(self.llm_client, "generate_structured"):
            return await self.llm_client.generate_structured(prompt, schema)
        else:
            # Fallback to plain generation
            response = await self._call_llm(prompt)
            return response


__all__ = [
    "AnswerSynthesizer",
    "StructuredAnswer",
]
