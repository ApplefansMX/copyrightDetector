from models.search_result import SearchResult
from search.search_provider import SearchProvider


class MockSearchProvider(SearchProvider):

    def search(self, query: str) -> list[SearchResult]:

        return [
            SearchResult(
                title="FernandaShows",
                url="https://x.com/fernandashows/status/123456",
                snippet="Publicación de FernandaShows",
                source="mock"
            ),
            SearchResult(
                title="FernandaShows video",
                url="https://example.com/video/123",
                snippet="Possible matching content",
                source="mock"
            )
        ]