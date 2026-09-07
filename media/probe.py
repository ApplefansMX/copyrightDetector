"""Bounded local-only subprocess access; no SDK or HTTP client."""
from dataclasses import dataclass, asdict
import json
import math
from pathlib import Path
import shutil
import subprocess


class MediaError(RuntimeError):
    pass


class ToolUnavailable(MediaError):
    pass


INPUT_POLICY = ["-protocol_whitelist", "file,pipe", "-format_whitelist", "mov,matroska,webm,avi,mpeg,mpegts,flv,ogg,asf"]


def executable(name):
    resolved = shutil.which(str(name))
    if resolved is None:
        raise ToolUnavailable(f"Required tool unavailable: {name}. Install FFmpeg/ffprobe or supply explicit paths.")
    return resolved


def local_file(value):
    text = str(value)
    if "://" in text or text.startswith(("\\\\", "//")):
        raise MediaError("Only local files accepted; URLs and network shares disabled")
    path = Path(value).expanduser().resolve(strict=True)
    if str(path).startswith(("\\\\", "//")):
        raise MediaError("Resolved path points to a network share")
    if not path.is_file():
        raise MediaError(f"Not a regular file: {path}")
    return path


def run(command, timeout):
    try:
        result = subprocess.run(command, capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise MediaError(f"Media operation exceeded {timeout}s") from exc
    if result.returncode:
        raise MediaError(result.stderr.decode("utf-8", errors="replace")[-2000:])
    return result.stdout


@dataclass(frozen=True)
class VideoInfo:
    path: str
    duration: float
    width: int
    height: int
    codec: str
    rotation: float
    sample_aspect_ratio: str

    def to_dict(self):
        return asdict(self)


def probe(path, ffprobe="ffprobe", timeout=180, max_duration=7200):
    path = local_file(path)
    raw = run([executable(ffprobe), "-v", "error", *INPUT_POLICY, "-show_streams", "-show_format", "-of", "json", str(path)], timeout)
    try:
        data = json.loads(raw)
        streams = [s for s in data.get("streams", []) if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")]
        if not streams:
            raise MediaError("File contains no usable video stream")
        stream = streams[0]
        duration = float(stream.get("duration") or data.get("format", {}).get("duration", 0))
        width, height = int(stream["width"]), int(stream["height"])
        if not math.isfinite(duration) or not 0 < duration <= max_duration:
            raise MediaError("Video duration missing, invalid or exceeds configured limit")
        if not 0 < width <= 16384 or not 0 < height <= 16384:
            raise MediaError("Invalid or excessive video dimensions")
        rotation = float(next((s["rotation"] for s in stream.get("side_data_list", []) if "rotation" in s), stream.get("tags", {}).get("rotate", 0)))
        if not math.isfinite(rotation):
            raise MediaError("Invalid rotation metadata")
        return VideoInfo(str(path), duration, width, height, stream.get("codec_name", "unknown"), rotation, stream.get("sample_aspect_ratio", "1:1"))
    except (KeyError, TypeError, ValueError) as exc:
        raise MediaError("Invalid ffprobe response or unsupported video metadata") from exc
