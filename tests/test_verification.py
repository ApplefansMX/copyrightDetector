import contextlib
import importlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from PIL import Image
from media.frames import Frame
from media.probe import MediaError, ToolUnavailable, executable, local_file, probe
from fingerprinting.visual import PerceptualHash, Observation, fingerprint_frames, hamming
from verification.config import Parameters
from verification.temporal import Match, retrieve, group_segments, coverage, union_duration
from verification.decision import decide
from evidence.report import write_report
from benchmarks.run import localization_iou


def picture(seed):
    rng = np.random.default_rng(seed)
    small = rng.integers(0, 256, (20, 20), dtype=np.uint8)
    return np.array(Image.fromarray(small).resize((160, 160), Image.Resampling.BICUBIC))


def observed(t, value, usable=True):
    return Observation(t, (value,), usable, 45, 6, False)


class FingerprintTests(unittest.TestCase):
    def setUp(self):
        self.d = PerceptualHash()
        self.p = Parameters(refine=False)

    def test_stable_and_distinct(self):
        a, b = picture(10), picture(99)
        self.assertEqual(self.d.compute(a), PerceptualHash().compute(a.copy()))
        self.assertGreater(self.d.distance(self.d.compute(a), self.d.compute(b)), 10)

    def test_hamming_known_vectors(self):
        self.assertEqual(hamming(0, 2**64-1), 64)
        self.assertEqual(hamming(0b1010, 0b1001), 2)
        self.assertEqual(hamming(123, 123), 0)

    def test_resize_jpeg_and_overlay(self):
        original = Image.fromarray(picture(14))
        jpeg = io.BytesIO()
        original.save(jpeg, format="JPEG", quality=55)
        altered = [np.array(Image.open(io.BytesIO(jpeg.getvalue()))),
                   np.array(original.resize((80, 60)).resize((160, 160)))]
        overlay = np.array(original).copy()
        overlay[8:20, 128:152] = 200
        altered.append(overlay)
        for frame in altered:
            self.assertLessEqual(self.d.distance(self.d.compute(np.array(original)), self.d.compute(frame)), self.p.max_hamming)

    def test_black_uniform_and_repeat_are_not_evidence(self):
        frames = [Frame(0, np.zeros((160,160), np.uint8)), Frame(1, np.full((160,160), 127, np.uint8)),
                  Frame(2, picture(3)), Frame(3, picture(3))]
        result = fingerprint_frames(frames, self.p, self.d)
        self.assertEqual([x.usable for x in result], [False, False, True, False])
        self.assertTrue(result[-1].repeated)

    def test_shuffled_frames_not_a_video_copy(self):
        frames = [Frame(t, picture(t+40)) for t in range(12)]
        originals = fingerprint_frames(frames, self.p, self.d)
        candidates = fingerprint_frames([Frame(t, frames[-1-t].pixels) for t in range(12)], self.p, self.d)
        matches, _ = retrieve(originals, candidates, self.d, self.p)
        self.assertGreater(len(matches), 8)
        self.assertEqual(group_segments(matches,12,12,self.p), [])

    def test_transformed_middle_sequence_end_to_end_in_memory(self):
        frames = [Frame(t, picture(t+100)) for t in range(24)]
        candidates = []
        for i, frame in enumerate(frames[6:18]):
            image = Image.fromarray(frame.pixels).resize((80,60)).resize((160,160))
            candidates.append(Frame(i, np.array(image)))
        of = fingerprint_frames(frames,self.p,self.d)
        cf = fingerprint_frames(candidates,self.p,self.d)
        matches, ambiguous = retrieve(of,cf,self.d,self.p)
        segments = group_segments(matches,24,12,self.p)
        report = decide(of,cf,segments,24,12,self.p,ambiguous)
        self.assertEqual(report["decision"], "probable_match")
        self.assertEqual(segments[0]["confidence_signals"]["offset_seconds"],6)
        self.assertGreater(report["candidate_coverage"], .8)


class TemporalTests(unittest.TestCase):
    def setUp(self):
        self.p = Parameters(refine=False)

    def test_retrieve_known_pairs_and_offset(self):
        original = [observed(10,0), observed(11,2**64-1)]
        candidate = [observed(0,0), observed(1,2**64-1)]
        matches, ambiguous = retrieve(original,candidate,PerceptualHash(),self.p)
        self.assertEqual([(m.original,m.candidate,m.offset) for m in matches],[(10,0,10),(11,1,10)])
        self.assertEqual(ambiguous,0)

    def test_ambiguous_motif_is_not_retrieved(self):
        matches, ambiguous = retrieve([observed(t,1) for t in range(10)], [observed(0,1)], PerceptualHash(),self.p)
        self.assertEqual(matches,[])
        self.assertEqual(ambiguous,1)

    def test_low_quality_not_retrieved(self):
        self.assertEqual(retrieve([observed(0,1,False)],[observed(0,1)],PerceptualHash(),self.p)[0],[])

    def test_pair_limit(self):
        with self.assertRaises(ValueError):
            retrieve([observed(0,1)]*3,[observed(0,1)]*3,PerceptualHash(),Parameters(max_pair_comparisons=4))

    def test_internal_cut_has_two_offsets(self):
        matches = [Match(t+5,t,2) for t in range(5)] + [Match(t+15,t,3) for t in range(5,10)]
        segments = group_segments(matches,40,10,self.p)
        self.assertEqual(len(segments),2)
        self.assertEqual([s["confidence_signals"]["offset_seconds"] for s in segments],[5,15])
        self.assertEqual([s["duration"] for s in segments],[4,4])

    def test_missing_one_sample_and_jitter(self):
        matches = [Match(t+7+(.1 if t%2 else 0),t,2) for t in [0,1,2,4,5,6]]
        segments = group_segments(matches,20,10,self.p)
        self.assertEqual(len(segments),1)
        self.assertAlmostEqual(segments[0]["duration"],6)

    def test_long_gap_splits_tracks(self):
        matches = [Match(t,t,0) for t in list(range(5))+list(range(12,17))]
        self.assertEqual(len(group_segments(matches,20,20,self.p)),2)

    def test_one_frame_and_scattered_matches_fail(self):
        self.assertEqual(group_segments([Match(0,0,0)],10,10,self.p),[])
        self.assertEqual(group_segments([Match(t*5,t,0) for t in range(8)],50,10,self.p),[])

    def test_union_coverage_not_double_counted(self):
        segments = [{"original_start":0,"original_end":8}, {"original_start":4,"original_end":10}]
        self.assertEqual(coverage(segments,"original",20),.5)
        self.assertEqual(union_duration([(0,10),(2,3),(9,12)]),12)
        self.assertEqual(coverage([],"original",0),0)

    def test_localization_iou(self):
        a=[{"candidate_start":0,"candidate_end":10}]
        b=[{"candidate_start":5,"candidate_end":15}]
        self.assertAlmostEqual(localization_iou(a,b,"candidate"),1/3)


class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.p=Parameters(refine=False)
        self.frames=[observed(t,t) for t in range(20)]

    def test_probable_partial_clip(self):
        segments=group_segments([Match(t+40,t,2) for t in range(12)],100,12,self.p)
        result=decide(self.frames,self.frames,segments,100,12,self.p)
        self.assertEqual(result["decision"],"probable_match")
        self.assertEqual(result["original_coverage"],.11)
        self.assertFalse(result["signals"]["calibrated"])
        json.dumps(result,allow_nan=False)

    def test_shared_intro_is_review_not_probable(self):
        segments=group_segments([Match(t,t,0) for t in range(5)],100,100,self.p)
        self.assertEqual(decide(self.frames,self.frames,segments,100,100,self.p)["decision"],"review")

    def test_no_coherence_is_no_match(self):
        self.assertEqual(decide(self.frames,self.frames,[],20,20,self.p)["decision"],"no_match")

    def test_no_frames_and_uniform_are_insufficient(self):
        for frames in ([],[observed(t,0,False) for t in range(20)]):
            self.assertEqual(decide(frames,self.frames,[],20,20,self.p)["decision"],"insufficient_evidence")

    def test_ambiguous_is_review(self):
        self.assertEqual(decide(self.frames,self.frames,[],20,20,self.p,8)["decision"],"review")


class SafetyAndCliTests(unittest.TestCase):
    def test_missing_ffmpeg(self):
        with patch("media.probe.shutil.which",return_value=None):
            with self.assertRaisesRegex(ToolUnavailable,"Required tool unavailable"):
                executable("ffmpeg")

    def test_invalid_and_non_video(self):
        with tempfile.TemporaryDirectory() as temp:
            file=Path(temp)/"bad.txt"
            file.write_text("not a video")
            with patch("media.probe.executable",return_value="ffprobe"), patch("media.probe.run",return_value=b'{"streams": []}'):
                with self.assertRaisesRegex(MediaError,"no usable video"):
                    probe(file)
            with patch("media.probe.executable",return_value="ffprobe"), patch("media.probe.run",return_value=b'not json'):
                with self.assertRaises(MediaError): probe(file)
            with self.assertRaises(FileNotFoundError): local_file(Path(temp)/"missing.mp4")

    def test_urls_and_network_shares_rejected(self):
        for value in ("https://example.com/video.mp4", "\\\\server\\share\\a.mp4"):
            with self.assertRaises(MediaError): local_file(value)

    def test_import_main_does_not_run_discovery(self):
        with patch("builtins.open",side_effect=AssertionError("Unexpected file access")):
            import main
            importlib.reload(main)

    def test_cli_missing_tool_is_structured_error(self):
        import main
        error=io.StringIO()
        with patch("media.probe.shutil.which",return_value=None), contextlib.redirect_stderr(error):
            code=main.main(["verify","original.mp4","candidate.mp4"])
        self.assertEqual(code,2)
        self.assertEqual(json.loads(error.getvalue())["error"],"ToolUnavailable")

    def test_report_never_overwrites_input(self):
        with tempfile.TemporaryDirectory() as temp:
            file=Path(temp)/"report.json"
            write_report({"decision":"review"},file)
            before=file.read_bytes()
            with self.assertRaises(FileExistsError): write_report({},file)
            self.assertEqual(before,file.read_bytes())

    def test_parameters_validate(self):
        for args in ({"sample_fps":0},{"max_hamming":80},{"refine":"false"},{"sample_fps":float("nan")},{"max_frames":1.5},{"probable_coverage":2}):
            with self.assertRaises(ValueError): Parameters(**args)


if __name__ == "__main__":
    unittest.main()
