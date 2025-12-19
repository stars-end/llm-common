"""Retrieval backend implementations."""

# Import pgvector backend if dependencies are available
try:
    from llm_common.retrieval.backends.pg_backend import (
        PgVectorBackend,
        create_pg_backend,
    )

    __all__ = [
        "PgVectorBackend",  # Recommended: Generic pgvector for Railway Postgres
        "create_pg_backend",  # Factory function for easy instantiation
    ]
except ImportError:
    # pgvector dependencies not installed
    __all__ = []
