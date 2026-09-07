import hashlib
import json
from pathlib import Path


class SearchCache:

    def __init__(self, cache_dir: str = "cache/serpapi"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(
            parents=True,
            exist_ok=True
        )

    def _get_cache_file(self, query: str, page: int) -> Path:

        value = f"{query}|{page}"

        cache_key = hashlib.sha256(
            value.encode("utf-8")
        ).hexdigest()

        return self.cache_dir / f"{cache_key}.json"

    def get(self, query: str, page: int):

        cache_file = self._get_cache_file(
            query,
            page
        )

        if not cache_file.exists():
            return None

        try:

            with cache_file.open(
                "r",
                encoding="utf-8"
            ) as file:
                return json.load(file)

        except (json.JSONDecodeError, OSError):

            return None

    def set(
        self,
        query: str,
        page: int,
        response: dict
    ):

        cache_file = self._get_cache_file(
            query,
            page
        )

        with cache_file.open(
            "w",
            encoding="utf-8"
        ) as file:
            json.dump(
                response,
                file,
                ensure_ascii=False,
                indent=2
            )