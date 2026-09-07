from dataclasses import asdict
import hashlib
import platform
import numpy as np
import PIL
from media.probe import probe, executable, run
from media.frames import extract_frames
from fingerprinting.visual import PerceptualHash, fingerprint_frames
from verification.config import Parameters
from verification.temporal import retrieve, group_segments
from verification.decision import decide

VERSION = "0.1.0-experimental"


def checksum(path):
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_files(original, candidate, parameters=None, ffmpeg="ffmpeg", ffprobe="ffprobe", descriptor=None):
    p = parameters or Parameters()
    ffmpeg, ffprobe = executable(ffmpeg), executable(ffprobe)
    oi = probe(original, ffprobe, p.timeout_seconds, p.max_duration)
    ci = probe(candidate, ffprobe, p.timeout_seconds, p.max_duration)
    descriptor = descriptor or PerceptualHash()
    def observations(info, start=0, end=None, fps=None):
        return fingerprint_frames(extract_frames(info, p, ffmpeg, start, end, fps), p, descriptor)
    original_frames, candidate_frames = observations(oi), observations(ci)
    matches, ambiguous = retrieve(original_frames, candidate_frames, descriptor, p)
    segments = group_segments(matches, oi.duration, ci.duration, p)
    refinements = 0
    if p.refine and p.refine_fps > p.sample_fps:
        refined = []
        for segment in segments:
            margin = 1 / p.sample_fps
            os, oe = max(0, segment["original_start"]-margin), min(oi.duration, segment["original_end"]+margin)
            cs, ce = max(0, segment["candidate_start"]-margin), min(ci.duration, segment["candidate_end"]+margin)
            if max(oe-os, ce-cs) * p.refine_fps > p.max_frames:
                refined.append(segment)
                continue
            of, cf = observations(oi, os, oe, p.refine_fps), observations(ci, cs, ce, p.refine_fps)
            if sum(x.usable for x in of) * sum(x.usable for x in cf) > p.max_pair_comparisons:
                refined.append(segment)
                continue
            dense_matches, _ = retrieve(of, cf, descriptor, p)
            offset = segment["confidence_signals"]["offset_seconds"]
            dense_matches = [m for m in dense_matches if abs(m.offset-offset) <= p.offset_tolerance]
            dense = group_segments(dense_matches, oi.duration, ci.duration, p, p.refine_fps)
            refined.extend(dense or [segment])
            refinements += bool(dense)
        segments = refined
    report = decide(original_frames, candidate_frames, segments, oi.duration, ci.duration, p, ambiguous)
    report["signals"].update({"retrieved_frame_pairs": len(matches), "refined_segments": refinements})
    report.update({"schema_version": "1", "original": {**oi.to_dict(), "sha256": checksum(oi.path)},
                   "candidate": {**ci.to_dict(), "sha256": checksum(ci.path)},
                   "algorithm": {"name": "temporal-visual-phash-baseline", "version": VERSION,
                                 "descriptor": descriptor.name, "threshold_status": "EXPERIMENTAL_UNCALIBRATED",
                                 "parameters": asdict(p), "runtime": {
                                     "python": platform.python_version(), "numpy": np.__version__, "pillow": PIL.__version__,
                                     "ffmpeg": run([ffmpeg, "-version"], p.timeout_seconds).decode().splitlines()[0],
                                     "ffprobe": run([ffprobe, "-version"], p.timeout_seconds).decode().splitlines()[0]}},
                   "limitations": ["Visual only; no audio analysis.", "Short or heavily transformed copies may be missed.",
                                    "No calibrated probability or legal authorization decision.",
                                    "Boundaries are sampling estimates relative to decoded start.",
                                    "Static or repeated material may be insufficient."]})
    return report
