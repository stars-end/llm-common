"""UnderstandPhase for intent and entity extraction.

Ported from Dexter's understand.ts - extracts intent and entities from user queries
before planning, enabling more targeted tool selection and execution.
"""

import logging

from pydantic import BaseModel, Field

from llm_common.core import LLMClient, LLMMessage, MessageRole

logger = logging.getLogger(__name__)


class Entity(BaseModel):
    """Extracted entity from user query."""

    type: str = Field(
        ...,
        description="Entity type: ticker, period, metric, comparison, or other",
    )
    value: str = Field(..., description="The extracted value")


class Understanding(BaseModel):
    """Result of the understand phase."""

    intent: str = Field(..., description="One-sentence description of user intent")
    entities: list[Entity] = Field(default_factory=list)


UNDERSTAND_SYSTEM_PROMPT = """You are an expert at understanding financial queries.
Extract the user's intent and any entities mentioned.

Entity types:
- ticker: Stock symbols (e.g., AAPL, NVDA, SPY, QQQ)
- period: Time periods (e.g., YTD, 1Y, Q3 2025, last month, since January)
- metric: Financial metrics (e.g., P/E ratio, revenue, dividends, market cap, beta)
- comparison: Comparison references (e.g., vs S&P 500, vs last year, compared to peers)
- other: Any other relevant entities

Be thorough in extracting all entities. The intent should be a single clear sentence.

Return a JSON object with:
{
  "intent": "one sentence describing what the user wants",
  "entities": [{"type": "ticker", "value": "AAPL"}, ...]
}"""


class UnderstandPhase:
    """Extract intent and entities from user query (ported from Dexter).

    This phase runs before planning to provide structured understanding
    of the user's query, enabling more targeted tool selection.

    Example:
        >>> phase = UnderstandPhase(llm_client)
        >>> result = await phase.run("What's NVDA's P/E ratio vs the S&P 500 YTD?")
        >>> result.intent
        "Compare NVIDIA's P/E ratio to the S&P 500 index year-to-date"
        >>> result.entities
        [Entity(type='ticker', value='NVDA'),
         Entity(type='metric', value='P/E ratio'),
         Entity(type='comparison', value='S&P 500'),
         Entity(type='period', value='YTD')]
    """

    def __init__(self, llm_client: LLMClient, model: str = "glm-4.5-air"):
        """Initialize UnderstandPhase.

        Args:
            llm_client: LLM client for making API calls
            model: Model to use for understanding (default: glm-4.5-air for speed)
        """
        self.llm = llm_client
        self.model = model

    async def run(
        self,
        query: str,
        conversation_context: str | None = None,
    ) -> Understanding:
        """Extract intent and entities from the query.

        Args:
            query: The user's question/request
            conversation_context: Optional formatted conversation history

        Returns:
            Understanding object with intent and entities
        """
        user_prompt = f'Query: "{query}"'
        if conversation_context:
            user_prompt = f"Previous conversation:\n{conversation_context}\n\n{user_prompt}"
        user_prompt += "\n\nExtract intent and entities as JSON."

        try:
            response = await self.llm.chat_completion(
                messages=[
                    LLMMessage(role=MessageRole.SYSTEM, content=UNDERSTAND_SYSTEM_PROMPT),
                    LLMMessage(role=MessageRole.USER, content=user_prompt),
                ],
                model=self.model,
                response_format={"type": "json_object"},
                temperature=0.0,
            )

            # Parse response
            result = Understanding.model_validate_json(response.content)
            logger.info(
                f"UnderstandPhase: intent='{result.intent}', " f"entities={len(result.entities)}"
            )
            return result

        except Exception as e:
            logger.warning(f"UnderstandPhase failed: {e}. Returning basic understanding.")
            # Fallback: return query as intent with no entities
            return Understanding(intent=query, entities=[])
