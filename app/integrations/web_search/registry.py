from functools import lru_cache

from app.config import get_settings
from app.integrations.web_search.base import WebSearchProvider
from app.integrations.web_search.mock import MockWebSearchProvider
from app.integrations.web_search.tavily import TavilyWebSearchProvider


@lru_cache
def get_web_search_provider() -> WebSearchProvider:
    settings = get_settings()
    provider = (settings.web_search_provider or "mock").lower()
    if provider == "tavily" and settings.tavily_api_key:
        return TavilyWebSearchProvider()
    return MockWebSearchProvider()
