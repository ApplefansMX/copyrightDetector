import json
from pathlib import Path


class PotentialUrlRepository:

    def __init__(self):
        self.file_path = (
            Path(__file__).resolve().parent.parent
            / "results"
            / "potential_urls.json"
        )

    def load(self):
        if not self.file_path.exists():
            return {
                "platforms": []
            }

        try:
            with open(
                self.file_path,
                "r",
                encoding="utf-8"
            ) as file:
                return json.load(file)

        except json.JSONDecodeError:
            return {
                "platforms": []
            }

    def save(self, data):
        self.file_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with open(
            self.file_path,
            "w",
            encoding="utf-8"
        ) as file:
            json.dump(
                data,
                file,
                indent=4,
                ensure_ascii=False
            )
            
    def add_url(self, platform, url):
        data = self.load()

        platforms = data["platforms"]

        platform_data = next(
            (
                item
                for item in platforms
                if item["platform"] == platform
            ),
            None
        )

        if platform_data is None:
            platform_data = {
                "platform": platform,
                "urls": []
            }

            platforms.append(platform_data)

        if url not in platform_data["urls"]:
            platform_data["urls"].append(url)

            self.save(data)