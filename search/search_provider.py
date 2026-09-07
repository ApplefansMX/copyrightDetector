from abc import ABC, abstractmethod

from models.search_result import SearchResult

class SearchProvider(ABC):

    @abstractmethod
    def search(self, query: str) -> list[SearchResult]:
        pass