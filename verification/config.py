"""All thresholds are EXPERIMENTAL, not calibrated probabilities."""
from dataclasses import dataclass, asdict
import math


@dataclass(frozen=True)
class Parameters:
    sample_fps: float = 1.0
    refine_fps: float = 4.0
    refine: bool = True
    frame_size: int = 160
    max_hamming: int = 10
    ambiguity_margin: int = 2
    max_alternatives: int = 3
    min_std: float = 12.0
    min_entropy: float = 3.0
    repeat_hamming: int = 2
    offset_tolerance: float = 0.65
    max_gap_seconds: float = 2.5
    min_matches: int = 4
    min_segment_seconds: float = 3.0
    probable_seconds: float = 8.0
    probable_coverage: float = 0.6
    max_duration: float = 7200.0
    max_frames: int = 8000
    max_pair_comparisons: int = 20000000
    timeout_seconds: float = 180.0

    def __post_init__(self):
        for name, value in asdict(self).items():
            if name == "refine":
                if not isinstance(value, bool):
                    raise ValueError("refine must be boolean")
                continue
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be a finite nonnegative number")
        for name in ("frame_size", "max_hamming", "ambiguity_margin", "max_alternatives", "repeat_hamming", "min_matches", "max_frames", "max_pair_comparisons"):
            if not isinstance(getattr(self, name), int):
                raise ValueError(f"{name} must be an integer")
        if not 0 < self.sample_fps <= self.refine_fps <= 30:
            raise ValueError("Require 0 < sample_fps <= refine_fps <= 30")
        if not 32 <= self.frame_size <= 512 or not 0 <= self.max_hamming <= 64:
            raise ValueError("Invalid frame size or Hamming threshold")
        if not 0 < self.probable_coverage <= 1 or self.min_matches < 2:
            raise ValueError("Invalid coverage or minimum matches")
        if min(self.max_frames, self.max_pair_comparisons, self.max_alternatives, self.max_duration, self.timeout_seconds, self.min_segment_seconds) <= 0:
            raise ValueError("Limits must be positive")
        if self.probable_seconds < self.min_segment_seconds:
            raise ValueError("probable_seconds must be >= min_segment_seconds")
        if self.max_gap_seconds < 1 / self.sample_fps:
            raise ValueError("max_gap_seconds must cover a sampling interval")
