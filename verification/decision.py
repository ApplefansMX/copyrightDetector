from verification.temporal import coverage, union_duration


def decide(original, candidate, segments, original_duration, candidate_duration, parameters, ambiguous=0):
    usable_o, usable_c = sum(x.usable for x in original), sum(x.usable for x in candidate)
    oc, cc = coverage(segments, "original", original_duration), coverage(segments, "candidate", candidate_duration)
    seconds = union_duration([(s["candidate_start"], s["candidate_end"]) for s in segments])
    signals = {"original_frames": len(original), "candidate_frames": len(candidate),
               "original_usable_frames": usable_o, "candidate_usable_frames": usable_c,
               "original_repeated_frames": sum(x.repeated for x in original),
               "candidate_repeated_frames": sum(x.repeated for x in candidate),
               "ambiguous_candidate_frames": ambiguous, "matched_candidate_seconds": seconds,
               "audio_evaluated": False, "calibrated": False}
    if min(usable_o, usable_c) < parameters.min_matches:
        decision, reason = "insufficient_evidence", "Too few informative, non-repeated visual observations."
    elif not segments:
        if ambiguous >= parameters.min_matches:
            decision, reason = "review", "Ambiguous motifs prevent a unique temporal alignment."
        else:
            decision, reason = "no_match", "No coherent visual segment passed experimental thresholds; absence of a copy is not proven."
    elif seconds >= parameters.probable_seconds and max(oc, cc) >= parameters.probable_coverage:
        decision, reason = "probable_match", "Coherent visual segments exceed experimental duration and coverage thresholds. Shared material, not a rights determination."
    else:
        decision, reason = "review", "Shared visual segment is short or limited in coverage; a shared intro/outro is possible."
    return {"decision": decision, "signals": signals, "matched_segments": segments,
            "original_coverage": oc, "candidate_coverage": cc, "reason": reason}
