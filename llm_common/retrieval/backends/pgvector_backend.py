"""Supabase pgvector backend for retrieval."""

from typing import Any, Callable, Optional
import uuid

from llm_common.retrieval.base import RetrievalBackend
from llm_common.retrieval.models import RetrievedChunk


class SupabasePgVectorBackend(RetrievalBackend):
    """Retrieval backend using Supabase Postgres with pgvector extension.

    This backend leverages existing Supabase infrastructure for cost-effective
    vector similarity search with native SQL support for metadata filtering.

    Example:
        ```python
        from supabase import create_client
        from llm_common.retrieval.backends import SupabasePgVectorBackend

        supabase = create_client(url, key)

        async def embed_query(text: str) -> list[float]:
            # Your embedding logic (OpenAI, local model, etc.)
            return embedding_vector

        backend = SupabasePgVectorBackend(
            supabase_client=supabase,
            table="document_chunks",
            vector_col="embedding",
            text_col="content",
            metadata_cols=["source", "section", "page"],
            embed_fn=embed_query
        )

        results = await backend.retrieve("What is RAG?", top_k=5)
        ```

    Args:
        supabase_client: Supabase client instance
        table: Name of the table containing vector embeddings
        vector_col: Name of the vector/embedding column (must be vector type)
        text_col: Name of the text content column
        metadata_cols: List of metadata column names to include in results
        embed_fn: Async function to generate embeddings from query text
        top_k_default: Default number of results to return
        rpc_function: Name of the RPC function for similarity search
                      (defaults to "match_{table}")
    """

    def __init__(
        self,
        supabase_client: Any,
        table: str,
        vector_col: str = "embedding",
        text_col: str = "content",
        metadata_cols: Optional[list[str]] = None,
        embed_fn: Optional[Callable[[str], Any]] = None,
        top_k_default: int = 5,
        rpc_function: Optional[str] = None,
        source_col: str = "source",
        id_col: str = "id",
    ) -> None:
        """Initialize the Supabase pgvector backend."""
        self.supabase = supabase_client
        self.table = table
        self.vector_col = vector_col
        self.text_col = text_col
        self.source_col = source_col
        self.id_col = id_col
        self.metadata_cols = metadata_cols or []
        self.embed_fn = embed_fn
        self.top_k_default = top_k_default
        self.rpc_function = rpc_function or f"match_{table}"

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        min_score: Optional[float] = None,
        filters: Optional[dict[str, Any]] = None,
    ) -> list[RetrievedChunk]:
        """Retrieve relevant chunks using pgvector similarity search.

        Args:
            query: Query text to search for
            top_k: Number of results to return (default: 5)
            min_score: Minimum similarity score threshold (0.0-1.0)
            filters: Dictionary of metadata filters (column: value)

        Returns:
            List of RetrievedChunk objects ordered by relevance

        Raises:
            ValueError: If embed_fn not provided and query embedding cannot be generated
            RuntimeError: If database query fails
        """
        # Generate query embedding
        if self.embed_fn is None:
            raise ValueError(
                "embed_fn must be provided to generate query embeddings. "
                "Pass an embedding function during initialization."
            )

        query_embedding = await self.embed_fn(query)

        # Ensure query_embedding is a list
        if not isinstance(query_embedding, list):
            # Handle case where embed_fn returns numpy array or other type
            query_embedding = list(query_embedding)

        # Build RPC call parameters
        rpc_params: dict[str, Any] = {
            "query_embedding": query_embedding,
            "match_count": top_k,
        }

        # Add similarity threshold if provided
        if min_score is not None:
            rpc_params["match_threshold"] = min_score

        # Execute similarity search via RPC function
        try:
            response = self.supabase.rpc(self.rpc_function, rpc_params).execute()
            results = response.data
        except Exception as e:
            # Fallback to direct SQL query if RPC function doesn't exist
            # This allows the backend to work with minimal setup
            results = await self._direct_similarity_search(
                query_embedding, top_k, min_score
            )

        # Apply metadata filters if provided
        if filters:
            results = [r for r in results if self._matches_filters(r, filters)]

        # Convert to RetrievedChunk objects
        chunks = []
        for result in results:
            # Extract metadata
            metadata = {}
            for col in self.metadata_cols:
                if col in result:
                    metadata[col] = result[col]

            chunks.append(
                RetrievedChunk(
                    content=result.get(self.text_col, ""),
                    score=float(result.get("similarity", 0.0)),
                    source=result.get(self.source_col, "unknown"),
                    metadata=metadata,
                    chunk_id=str(result.get(self.id_col, "")),
                    embedding=None,  # Don't return embeddings by default to save bandwidth
                )
            )

        return chunks

    async def query(
        self,
        embedding: list[float],
        k: int = 5,
        allowed_source_urls: Optional[list[str]] = None,
    ) -> list[RetrievedChunk]:
        """Query the vector store."""
        params: dict[str, Any] = {
            "query_embedding": embedding,
            "match_threshold": 0.0,  # TODO: Make configurable
            "match_count": k,
        }
        
        # Add filter if sources provided
        if allowed_source_urls:
            params["filter"] = {"source": {"in": allowed_source_urls}}
            
        response = self.client.rpc("match_documents", params).execute()
        
        chunks = []
        for match in response.data:
            chunks.append(
                RetrievedChunk(
                    content=match["content"],
                    source_url=match["source"],
                    # embedding=match["embedding"],  # RPC doesn't return embedding by default
                    metadata=match.get("metadata", {}),
                    score=match["similarity"],
                    document_id=match.get("document_id"),
                    chunk_index=match.get("chunk_index"),
                )
            )
            
        return chunks

    async def upsert(self, chunk: dict[str, Any]) -> str:
        """Upsert a chunk into the database.
        
        Args:
            chunk: Dictionary containing chunk data matching RetrievedChunk model
            
        Returns:
            str: ID of inserted/updated record
        """
        # Map internal keys to database columns
        # Expected schema: id, content, embedding, source, metadata, document_id, chunk_index
        
        # Extract fields
        content = chunk.get("content")
        embedding = chunk.get("embedding")
        source = chunk.get("source_url")
        metadata = chunk.get("metadata", {})
        chunk_id = chunk.get("id")
        
        if not content or not embedding:
            raise ValueError("Content and embedding are required for upsert")

        record = {
            "content": content,
            "embedding": embedding,
            "source": source,
        }
        
        if chunk_id:
            record[self.id_col] = chunk_id
        
        # Handle document_id (required by schema)
        document_id = chunk.get("document_id")
        if not document_id and "metadata" in chunk:
                document_id = chunk["metadata"].get("document_id") or chunk["metadata"].get("task_id")
        
        if not document_id:
                document_id = str(uuid.uuid4())
        
        record["document_id"] = document_id

        # Handle metadata - generic "metadata" column logic
        if "metadata" in chunk:
            record["metadata"] = chunk["metadata"]
            
        # Handle chunk_index
        if "chunk_index" in chunk:
            record["chunk_index"] = chunk["chunk_index"]

        # Perform upsert
        # Supabase-py .upsert() returns APIResponse
        response = self.client.table(self.table).upsert(record).execute()
        
        # Return ID from response
        if response.data and len(response.data) > 0:
            return str(response.data[0].get(self.id_col, ""))
        return ""

    async def _direct_similarity_search(
        self,
        query_embedding: list[float],
        top_k: int,
        min_score: Optional[float] = None,
    ) -> list[dict[str, Any]]:
        """Fallback direct SQL query for similarity search.

        Uses Supabase query builder with vector similarity function.
        """
        # Build column selection
        select_cols = [self.id_col, self.text_col, self.source_col] + self.metadata_cols

        # Build query
        query = self.supabase.table(self.table).select(",".join(select_cols))

        # Note: This is a simplified fallback. In production, you would:
        # 1. Use raw SQL with pgvector operators (<-> for L2 distance)
        # 2. Or ensure RPC function exists in your Supabase schema
        # For now, return empty results as this requires RPC function
        raise RuntimeError(
            f"RPC function '{self.rpc_function}' not found. "
            "Please create a similarity search function in your Supabase database. "
            "See documentation for example function."
        )

    def _matches_filters(self, result: dict[str, Any], filters: dict[str, Any]) -> bool:
        """Check if result matches all metadata filters."""
        for key, value in filters.items():
            if result.get(key) != value:
                return False
        return True

    async def get_by_id(self, chunk_id: str) -> Optional[RetrievedChunk]:
        """Retrieve a specific chunk by ID.

        Args:
            chunk_id: The unique identifier for the chunk

        Returns:
            RetrievedChunk if found, None otherwise
        """
        try:
            response = (
                self.supabase.table(self.table)
                .select("*")
                .eq(self.id_col, chunk_id)
                .execute()
            )

            if not response.data:
                return None

            result = response.data[0]

            # Extract metadata
            metadata = {}
            for col in self.metadata_cols:
                if col in result:
                    metadata[col] = result[col]

            return RetrievedChunk(
                content=result.get(self.text_col, ""),
                score=1.0,  # Direct retrieval has perfect match score
                source=result.get(self.source_col, "unknown"),
                metadata=metadata,
                chunk_id=str(result.get(self.id_col, "")),
            )
        except Exception:
            return None

    async def health_check(self) -> bool:
        """Check if the backend is healthy and can connect to Supabase.

        Returns:
            True if backend can connect, False otherwise
        """
        try:
            # Simple query to check connection
            response = self.supabase.table(self.table).select("count").limit(1).execute()
            return True
        except Exception:
            return False



    async def close(self) -> None:
        """Clean up resources.

        Supabase client handles connection pooling, so no explicit cleanup needed.
        """
        # Supabase client manages its own connection pool
        # No explicit cleanup needed
        pass
