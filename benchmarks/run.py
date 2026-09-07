"""Evaluate all benchmark cases, retaining failures and per-case evidence."""
import argparse
import json
from pathlib import Path
import time
from evidence.report import write_report
from verification.config import Parameters
from verification.pipeline import verify_files, checksum
from verification.temporal import union_duration


def localization_iou(expected, actual, axis):
    e = [(s[f"{axis}_start"], s[f"{axis}_end"]) for s in expected]
    a = [(s[f"{axis}_start"], s[f"{axis}_end"]) for s in actual]
    intersection = union_duration([(max(x,u), min(y,v)) for x,y in e for u,v in a if min(y,v) > max(x,u)])
    union = union_duration(e + a)
    return intersection / union if union else None


def evaluate(manifest, parameters=None, ffmpeg="ffmpeg", ffprobe="ffprobe"):
    p = parameters or Parameters()
    if checksum(manifest["original"]) != manifest["original_sha256"]:
        raise ValueError("Original changed since benchmark generation")
    rows = []
    for case in manifest["cases"]:
        started = time.perf_counter()
        row = {"name": case["name"], "label": case["label"]}
        try:
            if checksum(case["candidate"]) != case["candidate_sha256"]:
                raise ValueError("Candidate changed since manifest creation")
            report = verify_files(manifest["original"], case["candidate"], p, ffmpeg, ffprobe)
            row.update({"decision": report["decision"], "report": report,
                        "original_interval_iou": localization_iou(case["expected_segments"], report["matched_segments"], "original"),
                        "candidate_interval_iou": localization_iou(case["expected_segments"], report["matched_segments"], "candidate")})
        except (ValueError, OSError, RuntimeError) as exc:
            row.update({"decision": "error", "error": str(exc)})
        row["elapsed_seconds"] = time.perf_counter() - started
        rows.append(row)
    positive = [r for r in rows if r["label"] == "positive"]
    negative = [r for r in rows if r["label"] == "negative"]
    tp = sum(r["decision"] == "probable_match" for r in positive)
    fp = sum(r["decision"] == "probable_match" for r in negative)
    return {"threshold_status": "EXPERIMENTAL_UNCALIBRATED", "split": manifest.get("split", "UNASSIGNED"),
            "cases": rows, "metrics": {"positive_cases": len(positive), "negative_cases": len(negative),
                "strict_probable_precision": tp/(tp+fp) if tp+fp else None,
                "strict_probable_recall": tp/len(positive) if positive else None,
                "false_positive_rate": fp/len(negative) if negative else None,
                "positive_segment_detection_rate": sum(bool(r.get("report", {}).get("matched_segments")) for r in positive)/len(positive) if positive else None,
                "review_count": sum(r["decision"] == "review" for r in rows),
                "insufficient_count": sum(r["decision"] == "insufficient_evidence" for r in rows),
                "error_count": sum(r["decision"] == "error" for r in rows)},
            "warning": "Metrics describe only this dataset; review is not counted as an automatic positive. IoU measures interval coverage, not offset correctness."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--parameters", type=Path)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    args = parser.parse_args()
    overrides = json.loads(args.parameters.read_text(encoding="utf-8")) if args.parameters else {}
    report = evaluate(json.loads(args.manifest.read_text(encoding="utf-8")), Parameters(**overrides), args.ffmpeg, args.ffprobe)
    write_report(report, args.output)
    print(json.dumps(report["metrics"], indent=2))
    return 2 if report["metrics"]["error_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
