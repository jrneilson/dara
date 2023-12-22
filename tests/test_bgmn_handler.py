import unittest
from pathlib import Path

from dara.bgmn_worker import BGMNWorker


class TestBGMNHandler(unittest.TestCase):
    def test_bgmn_handler(self):
        example_path = (
            Path(__file__).parent.parent / "example" / "Mg3Ni3MnO8" / "Mg3Ni3MnO8.sav"
        )

        bgmn_handler = BGMNWorker()
        exit_code = bgmn_handler.run_refinement_cmd(example_path)
        self.assertEqual(exit_code, 0)
