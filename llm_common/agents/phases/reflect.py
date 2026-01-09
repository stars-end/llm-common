"""ReflectPhase for evaluating completeness and iteration control.

Ported from Dexter's reflect.ts - evaluates whether gathered data is sufficient
to answer the user's query, or if additional tool calls are needed.
"""

import logging

from pydantic import BaseModel, Field

from llm_common.agents.phases.understand import Understanding
from llm_common.core import LLMClient, LLMMessage, MessageRole

logger = logging.getLogger(__name__)


class ReflectionResult(BaseModel):
    """Result of the reflect phase."""

    is_complete: bool = Field(..., description="True if sufficient data gathered")
    reasoning: str = Field(..., description="Explanation of the decision")
    missing_info: list[str] = Field(
        default_factory=list, description="What's still needed (empty if complete)"
    )
    suggested_next_steps: str = Field(
        default="", description="Guidance for next iteration (empty if complete)"
    )


REFLECT_SYSTEM_PROMPT = """You are an expert evaluator for a financial research assistant.
Determine if the gathered data is SUFFICIENT to answer the user's query.

Guidelines:
- Be conservative: if important data is missing, say so
- Be practical: don't request unnecessary data
- Consider what the user actually asked for
- If tools failed or returned errors, note what's missing

Return a JSON object with:
{
  "is_complete": true/false,
  "reasoning": "why complete or not",
  "missing_info": ["list of what's still needed"] (empty if complete),
  "suggested_next_steps": "guidance for next iteration" (empty if complete)
}"""


class ReflectPhase:
    """Evaluate if gathered data is sufficient (ported from Dexter).

    This phase runs after tool execution to determine if:
    1. We have enough data to answer the query (is_complete=True)
    2. We need additional tool calls (is_complete=False with guidance)

    Example:
        >>> phase = ReflectPhase(llm_client, max_iterations=2)
        >>> result = await phase.run(
        ...     query="What's NVDA's P/E vs S&P 500?",
        ...     understanding=understanding,
        ...     completed_work="✓ Got NVDA P/E: 45.2\\n✗ Failed to get S&P 500 P/E",
        ...     iteration=0
        ... )
        >>> result.is_complete
        False
        >>> result.missing_info
        ["S&P 500 P/E ratio for comparison"]
    """

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "glm-4.5-air",
        max_iterations: int = 2,
    ):
        """Initialize ReflectPhase.

        Args:
            llm_client: LLM client for making API calls
            model: Model to use for reflection (default: glm-4.5-air for speed)
            max_iterations: Maximum iterations before forcing completion (default: 2)
        """
        self.llm = llm_client
        self.model = model
        self.max_iterations = max_iterations

    async def run(
        self,
        query: str,
        understanding: Understanding,
        completed_work: str,
        iteration: int,
    ) -> ReflectionResult:
        """Evaluate if gathered data is sufficient.

        Args:
            query: The original user query
            understanding: Result from UnderstandPhase
            completed_work: Formatted string of completed work with results
            iteration: Current iteration number (0-indexed)

        Returns:
            ReflectionResult indicating completion status and next steps
        """
        # Force completion on max iterations
        if iteration >= self.max_iterations:
            logger.info(
                f"ReflectPhase: Reached max iterations ({self.max_iterations}). "
                "Forcing completion."
            )
            return ReflectionResult(
                is_complete=True,
                reasoning=f"Reached maximum iterations ({self.max_iterations}). "
                "Proceeding with available data.",
                missing_info=[],
                suggested_next_steps="",
            )

        entities_str = ", ".join(f"{e.type}={e.value}" for e in understanding.entities) or "none"

        user_prompt = f"""Query: "{query}"
Intent: {understanding.intent}
Entities: {entities_str}
Iteration: {iteration + 1}/{self.max_iterations}

Completed Work:
{completed_work}

Is this sufficient to answer the query? Return JSON."""

        try:
            response = await self.llm.chat_completion(
                messages=[
                    LLMMessage(role=MessageRole.SYSTEM, content=REFLECT_SYSTEM_PROMPT),
                    LLMMessage(role=MessageRole.USER, content=user_prompt),
                ],
                model=self.model,
                response_format={"type": "json_object"},
                temperature=0.0,
            )

            result = ReflectionResult.model_validate_json(response.content)
            logger.info(
                f"ReflectPhase: is_complete={result.is_complete}, "
                f"missing={len(result.missing_info)} items"
            )
            return result

        except Exception as e:
            logger.warning(f"ReflectPhase failed: {e}. Assuming complete to avoid infinite loop.")
            return ReflectionResult(
                is_complete=True,
                reasoning=f"Reflection failed: {e}. Proceeding with available data.",
                missing_info=[],
                suggested_next_steps="",
            )

    def build_planning_guidance(self, reflection: ReflectionResult) -> str:
        """Build guidance string for next planning iteration.

        Args:
            reflection: Result from previous reflection

        Returns:
            Formatted guidance string for the planner
        """
        parts = [reflection.reasoning]
        if reflection.missing_info:
            parts.append(f"Missing information: {', '.join(reflection.missing_info)}")
        if reflection.suggested_next_steps:
            parts.append(f"Suggested next steps: {reflection.suggested_next_steps}")
        return "\n".join(parts)
