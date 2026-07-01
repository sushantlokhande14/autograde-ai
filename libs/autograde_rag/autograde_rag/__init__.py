"""RAG layer: chunk → embed → index → retrieve, with Redis caching.

Graders import ``retrieve`` in-process; the gRPC service in
``services/retrieval`` wraps the same function for out-of-process callers.
"""

from autograde_rag.chunk import Chunk, chunk_text
from autograde_rag.embed import embedding_dim, embed_texts

__all__ = ["Chunk", "chunk_text", "embed_texts", "embedding_dim"]
