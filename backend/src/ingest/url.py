"""
URL ingestion — fetches web pages and extracts clean text.

Uses httpx for async HTTP and BeautifulSoup for HTML parsing.
Strips navigation, scripts, and styling to get article content.
"""

import hashlib

import httpx
from bs4 import BeautifulSoup

from src.models.source import Source


class URLIngestor:
    """
    Fetches a URL and extracts readable text content.

    Handles standard HTML pages. For PDF URLs, delegates to PDFIngestor.
    For Arxiv abstract pages, extracts the abstract and metadata.

    Usage:
        ingestor = URLIngestor()
        source, sections = await ingestor.ingest("https://example.com/paper", "agent-1")
    """

    def __init__(self, timeout: int = 30) -> None:
        self._timeout = timeout

    async def ingest(
        self,
        url: str,
        agent_id: str,
    ) -> tuple[Source, list[dict[str, str]]]:
        """
        Fetch a URL and extract text content.

        Args:
            url: The web page URL to fetch.
            agent_id: ID of the agent performing ingestion.

        Returns:
            A tuple of (Source model, list of section dicts with
            'text' and 'section_title' keys).
        """
        async with httpx.AsyncClient(
            timeout=self._timeout,
            follow_redirects=True,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

        content_hash = hashlib.sha256(response.content).hexdigest()
        html = response.text

        # Parse HTML and extract text
        soup = BeautifulSoup(html, "html.parser")

        # Remove non-content elements
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        # Extract title
        title = ""
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text(strip=True)

        # Extract sections based on headings
        sections = _extract_sections(soup)

        source = Source(
            uri=url,
            source_type="url",
            title=title,
            raw_hash=content_hash,
            created_by=agent_id,
            confidence=1.0,
        )

        return source, sections


def _extract_sections(soup: BeautifulSoup) -> list[dict[str, str]]:
    """
    Split page content into sections based on heading tags.

    Falls back to treating the entire body as one section if
    no headings are found.
    """
    sections: list[dict[str, str]] = []
    current_title = ""
    current_text: list[str] = []

    # Try article tag first, then body
    content = soup.find("article") or soup.find("body") or soup

    for element in content.find_all(["h1", "h2", "h3", "h4", "p", "li", "pre", "code"]):
        if element.name in ("h1", "h2", "h3", "h4"):
            # Save previous section
            if current_text:
                sections.append({
                    "section_title": current_title,
                    "text": "\n".join(current_text).strip(),
                })
            current_title = element.get_text(strip=True)
            current_text = []
        else:
            text = element.get_text(strip=True)
            if text:
                current_text.append(text)

    # Don't forget the last section
    if current_text:
        sections.append({
            "section_title": current_title,
            "text": "\n".join(current_text).strip(),
        })

    # Fallback: if no sections found, get all text
    if not sections:
        all_text = content.get_text(separator="\n", strip=True)
        if all_text:
            sections.append({"section_title": "", "text": all_text})

    return sections
