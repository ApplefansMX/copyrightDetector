from dataclasses import dataclass
from pathlib import Path
import math
import tempfile
import numpy as np
from media.probe import executable, run, INPUT_POLICY, MediaError


@dataclass
class Frame:
    time: float
    pixels: np.ndarray


def extract_frames(info, parameters, ffmpeg="ffmpeg", start=0.0, end=None, fps=None):
    """Autorotate, preserve DAR and square pixels, then letterbox.

    Times are sampling-grid estimates relative to decoded start, not exact
    source timestamps. Decode before trimming avoids inaccurate keyframe seeks.
    """
    fps = fps or parameters.sample_fps
    end = min(info.duration, info.duration if end is None else end)
    if not 0 <= start < end:
        raise MediaError("Invalid extraction interval")
    count = math.ceil((end - start) * fps)
    if count > parameters.max_frames:
        raise MediaError("Sampling exceeds max_frames; reduce fps or raise explicit limit")
    size = parameters.frame_size
    # Fit directly into the bounded canvas; do not create an intermediate
    # full-resolution square-pixel image (large SAR could make it enormous).
    ratio = "if(gt(sar,0),dar,a)"
    filters = (f"setpts=PTS-STARTPTS,trim=start={start}:end={end},setpts=PTS-STARTPTS,"
               f"fps=fps={fps}:start_time=0,"
               f"scale=w='max(1,trunc({size}*min(1,{ratio})))':"
               f"h='max(1,trunc({size}/max(1,{ratio})))',setsar=1,"
               f"pad={size}:{size}:(ow-iw)/2:(oh-ih)/2,format=gray")
    with tempfile.TemporaryDirectory(prefix="local-video-frames-") as temp:
        output = Path(temp) / "frames.raw"
        run([executable(ffmpeg), "-nostdin", "-v", "error", "-threads", "1", *INPUT_POLICY,
             "-i", info.path, "-map", "0:V:0", "-an", "-sn", "-dn", "-vf", filters,
             "-frames:v", str(count), "-threads", "1", "-f", "rawvideo", str(output)], parameters.timeout_seconds)
        raw = np.fromfile(output, dtype=np.uint8)
    if raw.size % (size * size):
        raise MediaError("Truncated raw frame output")
    return [Frame(start + i / fps, pixels) for i, pixels in enumerate(raw.reshape((-1, size, size))) if start + i / fps < end]
