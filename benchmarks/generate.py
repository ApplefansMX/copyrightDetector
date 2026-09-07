"""Generate local transformations and ground-truth intervals from user media."""
import argparse
import json
from pathlib import Path
import shutil
from media.probe import probe, executable, run, INPUT_POLICY, local_file
from evidence.report import write_report
from verification.pipeline import checksum


def generate(original, output, negatives=(), ffmpeg="ffmpeg", ffprobe="ffprobe"):
    ffmpeg = executable(ffmpeg)
    info = probe(original, ffprobe)
    if info.duration < 20:
        raise ValueError("Provide an original of at least 20 seconds for this benchmark")
    negatives = [local_file(n) for n in negatives]
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    duration = info.duration
    start, end = duration * .2, duration * .8
    cases = []
    def interval(a, b, c=0):
        return {"original_start": a, "original_end": b, "candidate_start": c, "candidate_end": c+b-a}
    def add(name, filters=None, ranges=None, codec="mpeg4", quality="5", ext="mp4"):
        target = root / f"{name}.{ext}"
        command = [ffmpeg, "-nostdin", "-v", "error", "-n", *INPUT_POLICY, "-i", info.path,
                   "-map", "0:V:0", "-an", "-sn", "-dn"]
        if filters:
            command += ["-vf", filters]
        command += ["-c:v", codec]
        if codec == "mpeg4":
            command += ["-q:v", quality, "-pix_fmt", "yuv420p"]
        command += [str(target)]
        run(command, max(180, duration * 10))
        cases.append({"name": name, "candidate": str(target), "label": "positive",
                      "expected_segments": ranges or [interval(0, duration)], "command": command})
    identical = root / ("identical" + Path(info.path).suffix)
    shutil.copyfile(info.path, identical)
    cases.append({"name": "identical", "candidate": str(identical), "label": "positive", "expected_segments": [interval(0, duration)]})
    add("recompressed", quality="14")
    add("resolution", "scale=160:-2")
    add("codec", codec="ffv1", ext="mkv")
    add("trim_start", f"trim=start={start},setpts=PTS-STARTPTS", [interval(start, duration)])
    add("trim_end", f"trim=end={end},setpts=PTS-STARTPTS", [interval(0, end)])
    add("middle", f"trim=start={start}:end={end},setpts=PTS-STARTPTS", [interval(start, end)])
    add("watermark", "drawbox=x=iw*0.78:y=ih*0.05:w=iw*0.18:h=ih*0.10:color=white@0.6:t=fill")
    add("aspect_stretch", "scale=320:240,setsar=1")
    add("crop", "crop=trunc(iw*0.9/2)*2:trunc(ih*0.9/2)*2")
    add("combined", f"trim=start={start}:end={end},setpts=PTS-STARTPTS,scale=160:-2,drawbox=x=iw*0.8:y=0:w=iw*0.15:h=ih*0.08:color=white@0.5:t=fill", [interval(start, end)], quality="12")
    # concat is a local filter graph, never a playlist or external URL.
    cut1, cut2 = duration * .35, duration * .65
    target = root / "internal_cut.mp4"
    graph = (f"[0:V:0]split[a][b];[a]trim=end={cut1},setpts=PTS-STARTPTS[x];"
             f"[b]trim=start={cut2},setpts=PTS-STARTPTS[y];[x][y]concat=n=2:v=1:a=0[v]")
    command = [ffmpeg, "-nostdin", "-v", "error", "-n", *INPUT_POLICY, "-i", info.path,
               "-filter_complex", graph, "-map", "[v]", "-an", "-c:v", "mpeg4", "-q:v", "5", str(target)]
    run(command, max(180, duration * 10))
    cases.append({"name": "internal_cut", "candidate": str(target), "label": "positive", "command": command,
                  "expected_segments": [interval(0, cut1), interval(cut2, duration, cut1)]})
    for i, negative in enumerate(negatives):
        probe(negative, ffprobe)
        cases.append({"name": f"negative_{i}", "candidate": str(negative), "label": "negative", "expected_segments": []})
    for case in cases:
        case["candidate_sha256"] = checksum(case["candidate"])
    manifest = {"schema_version": "1", "split": "UNASSIGNED", "original": info.path,
                "original_sha256": checksum(info.path), "cases": cases,
                "warning": "Assign calibration/evaluation by original, not by derived file. No hard negatives are invented."}
    write_report(manifest, root / "manifest.json")
    return root / "manifest.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original")
    parser.add_argument("output", help="NEW directory outside version control")
    parser.add_argument("--negative", action="append", default=[])
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    args = parser.parse_args()
    print(generate(args.original, args.output, args.negative, args.ffmpeg, args.ffprobe))


if __name__ == "__main__":
    main()
