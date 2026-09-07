"""Monotonic runs with locally consistent offsets; supports internal cuts."""
from dataclasses import dataclass
from statistics import median


@dataclass(frozen=True)
class Match:
    original: float
    candidate: float
    distance: int

    @property
    def offset(self):
        return self.original - self.candidate


def retrieve(original, candidate, descriptor, parameters):
    originals = [x for x in original if x.usable]
    candidates = [x for x in candidate if x.usable]
    if len(originals) * len(candidates) > parameters.max_pair_comparisons:
        raise ValueError("Pair search exceeds max_pair_comparisons; reduce sampling or split inputs")
    matches, ambiguous = [], 0
    for c in candidates:
        ranked = sorted((descriptor.distance(o.hashes, c.hashes), o.time) for o in originals)
        if not ranked or ranked[0][0] > parameters.max_hamming:
            continue
        choices = [(d, t) for d, t in ranked if d <= min(parameters.max_hamming, ranked[0][0] + parameters.ambiguity_margin)]
        if len(choices) > parameters.max_alternatives:
            ambiguous += 1
            continue
        matches.extend(Match(t, c.time, d) for d, t in choices)
    return matches, ambiguous


def group_segments(matches, original_duration, candidate_duration, parameters, fps=None):
    fps = fps or parameters.sample_fps
    tracks, active = [], []
    for match in sorted(matches, key=lambda m: (m.candidate, m.distance, m.original)):
        active = [track for track in active if match.candidate-track[-1].candidate <= parameters.max_gap_seconds]
        possible = []
        for track in active:
            last = track[-1]
            if (0 < match.candidate - last.candidate <= parameters.max_gap_seconds
                and 0 < match.original - last.original <= parameters.max_gap_seconds
                and abs(match.offset - median(m.offset for m in track)) <= parameters.offset_tolerance):
                possible.append(track)
        if possible:
            min(possible, key=lambda t: abs(match.offset - median(m.offset for m in t))).append(match)
        else:
            track = [match]
            tracks.append(track)
            active.append(track)
    segments = []
    for track in tracks:
        if len(track) < parameters.min_matches:
            continue
        first, last = track[0], track[-1]
        duration = min(last.original-first.original, last.candidate-first.candidate)
        if duration < parameters.min_segment_seconds:
            continue
        os, oe = max(0, first.original), min(original_duration, last.original)
        cs, ce = max(0, first.candidate), min(candidate_duration, last.candidate)
        offset = median(m.offset for m in track)
        segments.append({"original_start": os, "original_end": oe, "candidate_start": cs,
                         "candidate_end": ce, "duration": min(oe-os, ce-cs),
                         "confidence_signals": {"matches": len(track), "median_hamming": median(m.distance for m in track),
                         "offset_seconds": offset, "max_offset_residual_seconds": max(abs(m.offset-offset) for m in track),
                         "sampling_interval_seconds": 1/fps, "boundary_uncertainty_seconds": 1/fps}})
    selected = []
    for segment in sorted(segments, key=lambda s: (-s["duration"], s["confidence_signals"]["median_hamming"])):
        if any(min(segment["candidate_end"], old["candidate_end"]) > max(segment["candidate_start"], old["candidate_start"]) for old in selected):
            continue
        selected.append(segment)
    return sorted(selected, key=lambda s: s["candidate_start"])


def union_duration(intervals):
    end, total = None, 0.0
    for start, stop in sorted(intervals):
        if stop < start:
            raise ValueError("Reversed interval")
        total += max(0, stop-max(start, end if end is not None else start))
        end = max(stop, end if end is not None else stop)
    return total


def coverage(segments, key, duration):
    if duration <= 0:
        return 0.0
    intervals = [(max(0, s[f"{key}_start"]), min(duration, s[f"{key}_end"])) for s in segments]
    return min(1.0, union_duration([(a,b) for a,b in intervals if b >= a]) / duration)
