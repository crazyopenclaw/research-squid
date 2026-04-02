"""
Plain text ingestion — handles raw text and markdown files.

The simplest ingester: reads text content and wraps it in a Source model.
"""

import hashlib
from pathlib import Path

from src.models.source import Source


class TextIngestor:
    """
    Ingests plain text or markdown content.

    Accepts either a file path or raw text string.

    Usage:
        ingestor = TextIngestor()
        source, sections = await ingestor.ingest_file("notes.md", "agent-1")
        source, sections = await ingestor.ingest_text("Some content...", "agent-1", title="My Notes")
    """

    async def ingest_file(
        self,
        file_path: str,
        agent_id: str,
    ) -> tuple[Source, list[dict[str, str]]]:
        """
        Read a text/markdown file and create a Source.

        Args:
            file_path: Path to the text file.
            agent_id: ID of the agent performing ingestion.

        Returns:
            A tuple of (Source model, list of section dicts).
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        content = path.read_text(encoding="utf-8")
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        source = Source(
            uri=str(path.absolute()),
            source_type="text",
            title=path.stem,
            raw_hash=content_hash,
            file_path=str(path),
            created_by=agent_id,
            confidence=1.0,
        )

        sections = _split_markdown_sections(content)
        return source, sections

    async def ingest_text(
        self,
        text: str,
        agent_id: str,
        title: str = "Untitled",
        uri: str = "",
    ) -> tuple[Source, list[dict[str, str]]]:
        """
        Create a Source from raw text content.

        Args:
            text: The text content.
            agent_id: ID of the agent performing ingestion.
            title: Optional title for the source.
            uri: Optional URI identifier.

        Returns:
            A tuple of (Source model, list of section dicts).
        """
        content_hash = hashlib.sha256(text.encode()).hexdigest()

        source = Source(
            uri=uri or f"text://{content_hash[:12]}",
            source_type="text",
            title=title,
            raw_hash=content_hash,
            created_by=agent_id,
            confidence=1.0,
        )

        sections = _split_markdown_sections(text)
        return source, sections


def _split_markdown_sections(text: str) -> list[dict[str, str]]:
    """
    Split text into sections based on markdown headings.

    Falls back to a single section if no headings are found.
    """
    sections: list[dict[str, str]] = []
    current_title = ""
    current_lines: list[str] = []

    for line in text.split("\n"):
        if line.startswith("#"):
            # Save previous section
            if current_lines:
                sections.append({
                    "section_title": current_title,
                    "text": "\n".join(current_lines).strip(),
                })
            current_title = line.lstrip("#").strip()
            current_lines = []
        else:
            current_lines.append(line)

    # Last section
    if current_lines:
        sections.append({
            "section_title": current_title,
            "text": "\n".join(current_lines).strip(),
        })

    if not sections:
        sections.append({"section_title": "", "text": text.strip()})

    return sections
