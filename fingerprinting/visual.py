"""64-bit DCT pHash with NumPy/Pillow; not ImageHash-bit-compatible."""
from dataclasses import dataclass
from typing import Protocol
import numpy as np
from PIL import Image


class Descriptor(Protocol):
    name: str
    def compute(self, pixels: np.ndarray) -> tuple[int, ...]: ...
    def distance(self, a: tuple[int, ...], b: tuple[int, ...]) -> int: ...


def hamming(a, b):
    return (int(a) ^ int(b)).bit_count()


def unletterbox(pixels):
    # Remove very dark uniform borders only, capped at 25% per edge.
    h, w = pixels.shape
    top, bottom, left, right = 0, h, 0, w
    def dark(row):
        return float(np.mean(row)) < 10 and float(np.std(row)) < 3
    while top < h // 4 and dark(pixels[top]): top += 1
    while bottom > 3 * h // 4 and dark(pixels[bottom - 1]): bottom -= 1
    while left < w // 4 and dark(pixels[top:bottom, left]): left += 1
    while right > 3 * w // 4 and dark(pixels[top:bottom, right - 1]): right -= 1
    return pixels[top:bottom, left:right]


class PerceptualHash:
    name = "numpy-dct-phash64-full-center85-v1"

    def __init__(self):
        n = np.arange(32)
        self.basis = np.cos(np.pi / 32 * (n[None, :] + .5) * n[:, None])
        self.basis[0] *= 1 / np.sqrt(2)
        self.basis *= np.sqrt(2 / 32)

    def hash_image(self, pixels):
        image = Image.fromarray(np.asarray(pixels, dtype=np.uint8)).resize((32, 32), Image.Resampling.LANCZOS)
        dct = self.basis @ np.asarray(image, dtype=float) @ self.basis.T
        low = dct[:8, :8].flatten()
        bits = low > np.median(low[1:])
        bits[0] = False
        return int.from_bytes(np.packbits(bits).tobytes(), "big")

    def compute(self, pixels):
        pixels = unletterbox(pixels)
        h, w = pixels.shape
        dy, dx = max(1, round(h * .075)), max(1, round(w * .075))
        return self.hash_image(pixels), self.hash_image(pixels[dy:h-dy, dx:w-dx])

    def distance(self, a, b):
        return min(hamming(x, y) for x in a for y in b)


@dataclass(frozen=True)
class Observation:
    time: float
    hashes: tuple[int, ...]
    usable: bool
    std: float
    entropy: float
    repeated: bool


def fingerprint_frames(frames, parameters, descriptor):
    observations, previous = [], None
    for frame in frames:
        pixels = unletterbox(frame.pixels)
        hist = np.bincount(pixels.ravel(), minlength=256).astype(float)
        probabilities = hist[hist > 0] / pixels.size
        entropy = float(-np.sum(probabilities * np.log2(probabilities)))
        std = float(np.std(pixels))
        hashes = descriptor.compute(frame.pixels)
        repeated = previous is not None and hamming(previous[0], hashes[0]) <= parameters.repeat_hamming
        usable = std >= parameters.min_std and entropy >= parameters.min_entropy and not repeated
        observations.append(Observation(frame.time, hashes, usable, std, entropy, repeated))
        previous = hashes
    return observations
