"""
Source and SourceChunk models — representing ingested research material.

A Source is a complete document (PDF, URL, or plain text). SourceChunks
are semantic segments of a Source, sized for embedding and RAG retrieval.
"""

from typing import Literal

from pydantic import Field

from src.models.base import BaseArtifact


SourceType = Literal["pdf", "url", "text", "arxiv"]


class Source(BaseArtifact):
    """
    An ingested research document.

    Tracks the original URI, document type, and a content hash to
    prevent duplicate ingestion.
    """

    uri: str = Field(
        ...,
        description="Original location — file path, URL, or arxiv ID.",
    )
    source_type: SourceType = Field(
        ...,
        description="How this source was acquired.",
    )
    title: str = Field(
        default="",
        description="Human-readable title extracted from the document.",
    )
    raw_hash: str = Field(
        default="",
        description="SHA-256 hash of raw content for deduplication.",
    )
    summary: str = Field(
        default="",
        description="Top-level summary generated during ingestion.",
    )
    file_path: str = Field(
        default="",
        description="Local path in data/sources/ where the raw file is stored.",
    )


class SourceChunk(BaseArtifact):
    """
    A semantic chunk extracted from a Source.

    Each chunk is small enough to embed (512–1024 tokens) and carries
    its position within the parent document for ordering.
    """

    source_id: str = Field(
        ...,
        description="ID of the parent Source this chunk belongs to.",
    )
    text: str = Field(
        ...,
        description="The chunk's text content.",
    )
    chunk_index: int = Field(
        ...,
        description="Position of this chunk within the parent source (0-indexed).",
    )
    embedding_id: str = Field(
        default="",
        description="ID in the pgvector embeddings table, set after embedding.",
    )
    section_title: str = Field(
        default="",
        description="Section/heading this chunk falls under, if available.",
    )
