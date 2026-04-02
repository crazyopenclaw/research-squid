"""
Tavily web search integration.

Tavily returns clean, extracted content (not just URLs), making it
ideal for AI agents that need to read web content directly. Agents
use this to discover relevant sources beyond user-provided material.
"""

try:
    from tavily import AsyncTavilyClient
    _HAS_TAVILY = True
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    AsyncTavilyClient = object
    _HAS_TAVILY = False

from src.config import Settings, settings as default_settings
from src.events.bus import EventBus
from src.models.events import Event, EventType


class TavilySearch:
    """
    Web search via the Tavily API.

    Returns structured results with extracted content, ready for
    ingestion into the knowledge graph.

    Usage:
        search = TavilySearch(settings, event_bus)
        results = await search.search("antibiotic resistance mechanisms")
    """

    def __init__(
        self,
        config: Settings | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._config = config or default_settings
        self._bus = event_bus
        self._client: AsyncTavilyClient | None = None

    def _get_client(self) -> AsyncTavilyClient:
        """Lazily initialize the Tavily client."""
        if not _HAS_TAVILY:
            raise RuntimeError(
                "The optional 'tavily' package is not installed. "
                "Install backend extras or add 'tavily-python' to the "
                "environment to enable Tavily search."
            )
        if not self._client:
            if not self._config.tavily_api_key:
                raise ValueError(
                    "TAVILY_API_KEY not set. Add it to .env or environment."
                )
            self._client = AsyncTavilyClient(api_key=self._config.tavily_api_key)
        return self._client

    async def search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "advanced",
        agent_id: str = "",
    ) -> list[dict]:
        """
        Search the web for relevant content.

        Args:
            query: Natural language search query.
            max_results: Maximum number of results to return.
            search_depth: "basic" for speed, "advanced" for quality.
            agent_id: ID of the agent performing the search.

        Returns:
            List of dicts with 'title', 'url', 'content', and 'score' keys.
        """
        client = self._get_client()

        response = await client.search(
            query=query,
            max_results=max_results,
            search_depth=search_depth,
            include_answer=False,
        )

        results = []
        for item in response.get("results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
                "score": item.get("score", 0.0),
            })

        # Emit discovery event
        if self._bus and results:
            await self._bus.publish(Event(
                event_type=EventType.SOURCE_DISCOVERED,
                agent_id=agent_id,
                payload={
                    "query": query,
                    "results_count": len(results),
                    "source": "tavily",
                },
            ))

        return results
