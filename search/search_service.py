from models.search_result import SearchResult
from search.search_provider import SearchProvider
from utils.url_utils import is_authorized_url

class SearchService:

    def __init__(
        self,
        provider: SearchProvider,
        authorized_profiles: list[dict]
    ):
        self.provider = provider
        self.authorized_profiles = authorized_profiles

    def search(self, query: str) -> list[SearchResult]:
        results = self.provider.search(query)

        for result in results:
            result.authorized = is_authorized_url(
                result.url,
                self.authorized_profiles
            )

        return results