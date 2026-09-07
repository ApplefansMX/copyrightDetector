"""Actual encoder/decoder tests. Synthetic media stays in temporary directories."""
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from PIL import Image
from tests.test_verification import picture
from benchmarks.generate import generate
from verification.pipeline import verify_files
from verification.config import Parameters
from media.probe import run, MediaError

FFMPEG=os.environ.get("FFMPEG","ffmpeg")
FFPROBE=os.environ.get("FFPROBE","ffprobe")
AVAILABLE=bool(shutil.which(FFMPEG) and shutil.which(FFPROBE))


@unittest.skipUnless(AVAILABLE,"FFmpeg/ffprobe unavailable; real video integration NOT executed")
class VideoIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix="video-baseline-tests-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root=Path(cls.temp.name)
        cls.original=cls.make_video("original",100)
        cls.negative=cls.make_video("negative",900)
        path=generate(cls.original,cls.root/"derived",[cls.negative],FFMPEG,FFPROBE)
        cls.manifest=json.loads(path.read_text(encoding="utf-8"))

    @classmethod
    def make_video(cls,name,seed):
        folder=cls.root/name
        folder.mkdir()
        for i in range(24):
            Image.fromarray(picture(seed+i)).save(folder/f"{i:03d}.png")
        target=cls.root/f"{name}.mp4"
        run([FFMPEG,"-nostdin","-v","error","-framerate","1","-i",str(folder/"%03d.png"),
             "-r","4","-c:v","mpeg4","-q:v","3","-pix_fmt","yuv420p",str(target)],120)
        return target

    def test_transformation_suite(self):
        for case in self.manifest["cases"]:
            with self.subTest(case=case["name"]):
                report=verify_files(self.original,case["candidate"],Parameters(),FFMPEG,FFPROBE)
                json.dumps(report,allow_nan=False)
                if case["label"]=="negative":
                    self.assertEqual(report["decision"],"no_match")
                else:
                    self.assertIn(report["decision"],("probable_match","review"))
                    self.assertTrue(report["matched_segments"])
                    if case["name"] in ("identical","middle","resolution","recompressed"):
                        self.assertEqual(report["decision"],"probable_match")
                    if case["name"]=="internal_cut":
                        self.assertGreaterEqual(len(report["matched_segments"]),2)

    def test_invalid_real_file(self):
        invalid=self.root/"invalid.txt"
        invalid.write_text("not video")
        with self.assertRaises(MediaError):
            verify_files(self.original,invalid,Parameters(),FFMPEG,FFPROBE)

    def test_real_black_video_insufficient(self):
        target=self.root/"black.mp4"
        run([FFMPEG,"-nostdin","-v","error","-f","lavfi","-i","color=black:s=160x160:r=4:d=12", "-c:v","mpeg4",str(target)],120)
        report=verify_files(target,target,Parameters(),FFMPEG,FFPROBE)
        self.assertEqual(report["decision"],"insufficient_evidence")


if __name__=="__main__":
    unittest.main()
