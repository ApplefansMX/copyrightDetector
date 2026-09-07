from urllib.parse import urlparse


def classify_url(url: str) -> str:

    parsed = urlparse(url)
    #print(parsed)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    query = parsed.query.lower()

    # -------------------------
    # SEARCH
    # -------------------------

    search_patterns = [
        "/search",
        "/discover",
        "/popular"
    ]

    if any(pattern in path for pattern in search_patterns):
        return "SEARCH"

    if "search_query" in query:
        return "SEARCH"

    # -------------------------
    # EROME
    # -------------------------

    if host.endswith("erome.com"):
        if path.startswith("/a/"):
            return "CONTENT"

    # -------------------------
    # X / TWITTER
    # -------------------------
    #print(path)
    if host in ["x.com", "twitter.com"]:

        if path.startswith("/i/broadcasts/"):
            return "CONTENT"

    # -------------------------
    # TIKTOK
    # -------------------------

    if host.endswith("tiktok.com"):

        if "/video/" in path:
            return "CONTENT"

        if "/@" in path:
            return "PROFILE"

    # -------------------------
    # DEFAULT
    # -------------------------

    return "UNKNOWN"