from dataclasses import dataclass

@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str
    authorized: bool = False
    url_type: str = "UNKNOWN"