import json
import argparse
import sys
from pathlib import Path
def load_authorizedProfiles():
    with open("originals/authorizedProfiles.json", "r", encoding="utf-8") as file:
        return json.load(file)

def load_config():
    with open("config.json", "r", encoding="utf-8") as file:
        return json.load(file)



def discovery():
    from search.serpapi_search_provider import SerpApiSearchProvider
    from cache.search_cache import SearchCache
    from storage.potential_url_repository import PotentialUrlRepository
    from utils.url_utils import get_platform
    authorizedProfiles = load_authorizedProfiles()
    config = load_config()
    
    authorized_profiles = authorizedProfiles["authorizedProfiles"]
    
    serp_api_config = config["search"]["serpApi"]
    
    cache = SearchCache()
    
    repository = PotentialUrlRepository()
    
    provider = SerpApiSearchProvider(
        api_key=serp_api_config["apiKey"],
        cache=cache,
        authorized_profiles=authorized_profiles
    )
    
    results = provider.search(
        "x-video.tube fernandashows fernandashows",
        pages=5
    )
    
    # for result in results:
    #     print(result.title)
    #     print(result.url)
    #     print()
    
    for result in results:
    
        status = (
            "AUTHORIZED"
            if result.authorized
            else "POTENTIAL"
        )
        if status == "POTENTIAL" and result.url_type != "SEARCH":
    
            platform = get_platform(result.url)
    
            repository.add_url(
                platform,
                result.url
            )
    
            print(
                f"[{status}] "
                f"[{result.url_type}] "
                f"{result.title}"
            )
    
            print(f"  {result.url}")
            print()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Local visual video verification")
    commands = parser.add_subparsers(dest="command", required=True)
    verify = commands.add_parser("verify", help="Compare local files without network access")
    verify.add_argument("original")
    verify.add_argument("candidate")
    verify.add_argument("--output", type=Path, help="New JSON report; existing files are never overwritten")
    verify.add_argument("--parameters", type=Path, help="JSON overrides for experimental parameters")
    verify.add_argument("--sample-fps", type=float)
    verify.add_argument("--ffmpeg", default="ffmpeg")
    verify.add_argument("--ffprobe", default="ffprobe")
    commands.add_parser("discovery", help="Original ONLINE experiment; consumes API credits")
    args = parser.parse_args(argv)
    if args.command == "discovery":
        discovery()
        return 0
    try:
        from verification.config import Parameters
        from verification.pipeline import verify_files
        from evidence.report import write_report
        overrides = json.loads(args.parameters.read_text(encoding="utf-8")) if args.parameters else {}
        if args.sample_fps is not None:
            overrides["sample_fps"] = args.sample_fps
        report = verify_files(args.original, args.candidate, Parameters(**overrides), args.ffmpeg, args.ffprobe)
        if args.output:
            write_report(report, args.output)
        print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (ValueError, TypeError, OSError, RuntimeError, ImportError) as exc:
        print(json.dumps({"error": type(exc).__name__, "reason": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
    
