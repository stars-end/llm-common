"""
RAG Pipeline Stories for Affordabot verification.

These stories cover the full RAG pipeline from discovery to LLM analysis.
Import these into affordabot's unified_verify.py.
"""

from ..framework import VerificationStory, StoryCategory


def get_rag_stories() -> list[VerificationStory]:
    """
    Return all RAG pipeline verification stories.
    
    Stories cover:
    - Phase 0-1: Environment & Discovery (LLM query generation)
    - Phase 2-5: Search, Ingestion, Embedding, Vector Store
    - Phase 6-10: Retrieval, Research, Generate, Review, Refine
    - Phase 11: Admin UI visual validation
    """
    return [
        VerificationStory(
            id="rag_00_env",
            name="Environment Check",
            category=StoryCategory.RAG_PIPELINE,
            phase=0,
            requires_browser=False,
            requires_llm=False,
            description="Verify all required environment variables are set",
        ),
        VerificationStory(
            id="rag_01_discovery",
            name="Discovery: LLM Query Generation",
            category=StoryCategory.RAG_PIPELINE,
            phase=1,
            requires_browser=False,
            requires_llm=True,
            llm_model="glm-4.7",
            description="Generate search queries using GLM-4.7",
        ),
        VerificationStory(
            id="rag_02_search",
            name="Search: Z.ai Web Search",
            category=StoryCategory.RAG_PIPELINE,
            phase=2,
            requires_browser=False,
            requires_llm=True,
            llm_model="glm-4.5",  # Web search uses 4.5
            description="Execute web search with generated queries",
        ),
        VerificationStory(
            id="rag_03_ingest",
            name="Ingestion: Chunk Creation",
            category=StoryCategory.RAG_PIPELINE,
            phase=3,
            requires_browser=False,
            requires_llm=False,
            description="Create document chunks from scraped content",
        ),
        VerificationStory(
            id="rag_04_embed",
            name="Embedding: OpenRouter",
            category=StoryCategory.RAG_PIPELINE,
            phase=4,
            requires_browser=False,
            requires_llm=True,
            llm_model="qwen/qwen3-embedding-8b",
            description="Generate embeddings via OpenRouter",
        ),
        VerificationStory(
            id="rag_05_vector",
            name="Vector Store: PgVector Insert",
            category=StoryCategory.RAG_PIPELINE,
            phase=5,
            requires_browser=False,
            requires_llm=False,
            description="Insert embeddings into PgVector",
        ),
        VerificationStory(
            id="rag_06_retrieve",
            name="Retrieval: Similarity Search",
            category=StoryCategory.RAG_PIPELINE,
            phase=6,
            requires_browser=False,
            requires_llm=False,
            description="Query PgVector for similar documents",
        ),
        VerificationStory(
            id="rag_07_research",
            name="Research: LLM Research Step",
            category=StoryCategory.RAG_PIPELINE,
            phase=7,
            requires_browser=False,
            requires_llm=True,
            llm_model="glm-4.6",
            description="Execute research step with Z.ai + pgvector",
        ),
        VerificationStory(
            id="rag_08_generate",
            name="Generate: Cost Analysis",
            category=StoryCategory.RAG_PIPELINE,
            phase=8,
            requires_browser=False,
            requires_llm=True,
            llm_model="glm-4.6",
            description="Generate cost impact analysis",
        ),
        VerificationStory(
            id="rag_09_review",
            name="Review: Critique Step",
            category=StoryCategory.RAG_PIPELINE,
            phase=9,
            requires_browser=False,
            requires_llm=True,
            llm_model="glm-4.6",
            description="Review and critique generated analysis",
        ),
        VerificationStory(
            id="rag_10_refine",
            name="Refine: Final Polish",
            category=StoryCategory.RAG_PIPELINE,
            phase=10,
            requires_browser=False,
            requires_llm=True,
            llm_model="glm-4.6",
            description="Refine analysis based on critique",
        ),
        VerificationStory(
            id="rag_11_admin",
            name="Admin UI: Visual Validation",
            category=StoryCategory.RAG_PIPELINE,
            phase=11,
            requires_browser=True,
            requires_llm=True,
            llm_model="glm-4.6v",
            screenshot_selector="body",
            glm_prompt="Analyze this admin dashboard screenshot. Describe the main sections, navigation, and any data displayed. Confirm the UI is rendering correctly.",
            description="Visual validation of admin dashboard using GLM-4.6V",
        ),
    ]
