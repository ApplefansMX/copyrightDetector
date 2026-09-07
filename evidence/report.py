import json
from pathlib import Path


def write_report(report, output):
    """Exclusive creation prevents overwriting input files or existing evidence."""
    encoded = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
    with Path(output).open("x", encoding="utf-8") as file:
        file.write(encoded + "\n")
