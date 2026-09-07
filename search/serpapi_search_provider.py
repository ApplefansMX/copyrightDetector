import serpapi

from cache.search_cache import SearchCache
from models.search_result import SearchResult
from search.search_provider import SearchProvider
from utils.url_classifier import classify_url
from utils.url_utils import is_authorized_url

class SerpApiSearchProvider(SearchProvider):

    def __init__(
        self,
        api_key: str,
        cache: SearchCache,
        authorized_profiles: list[dict]
    ):
        self.api_key = api_key
        self.cache = cache
        self.authorized_profiles = authorized_profiles

    def search(
        self,
        query: str,
        pages: int = 1
    ) -> list[SearchResult]:

        all_results = []

        for page in range(1, pages + 1):

            cached_response = self.cache.get(
                query,
                page
            )

            if cached_response is not None:

                print(
                    f"[CACHE] Usando resultado almacenado: "
                    f"'{query}' página {page}"
                )

                results = cached_response

            else:

                print(
                    f"[SERPAPI] Ejecutando búsqueda: "
                    f"'{query}' página {page}"
                )

                client = serpapi.Client(
                    api_key=self.api_key
                )

                results = client.search({
                    "engine": "google",
                    "q": query,
                    "start": (page - 1) * 10
                })

                results = dict(results)

                self.cache.set(
                    query,
                    page,
                    results
                )

            for item in results.get(
                "organic_results",
                []
            ):

                result = SearchResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                    source="google",
                    authorized=is_authorized_url(
                        item.get("link", ""),
                        self.authorized_profiles
                    ),
                    url_type=classify_url(
                        item.get("link", "")
                    )
                )

                all_results.append(result)

        return all_results