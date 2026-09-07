import requests

from models.search_result import SearchResult
from search.search_provider import SearchProvider


class WebSearchProvider(SearchProvider):

    def __init__(self, api_key: str, search_engine_id: str):
        self.api_key = api_key
        self.search_engine_id = search_engine_id

    def search(self, query: str) -> list[SearchResult]:

        url = "https://www.googleapis.com/customsearch/v1"

        params = {
            "key": self.api_key,
            "cx": self.search_engine_id,
            "q": query
        }

        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        results = []

        for item in data.get("items", []):

            result = SearchResult(
                title=item.get("title", ""),
                url=item.get("link", ""),
                snippet=item.get("snippet", ""),
                source="google"
            )

            results.append(result)

        return results