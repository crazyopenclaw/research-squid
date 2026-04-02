"""
Source ingestion pipeline — PDF, URL, and plain text to chunks.

Each ingester reads a specific format, extracts clean text, and
passes it to the chunker. The chunker splits text into semantic
segments sized for embedding and RAG retrieval.
"""
