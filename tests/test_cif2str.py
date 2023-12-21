import unittest
import warnings
from pathlib import Path
from tempfile import TemporaryDirectory

from spglib import get_error_message

from ar3l_search.cif2str import cif2str


class TestCIF2STR(unittest.TestCase):
    def test_cif2str(self):
        folders = Path(__file__).parent.parent / "example" / "summary_v2"

        with TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            cif_count = 0
            for folder in folders.glob("*"):
                if folder.is_dir():
                    for cif_path in (folder / "phases").glob("*.cif"):
                        try:
                            cif2str(cif_path, tmpdir)
                        except Exception as e:
                            print(f"Error in {cif_path}")
                            print(get_error_message())
                            raise e
                        cif_count += 1
                        self.assertTrue((tmpdir / f"{cif_path.stem}.str").exists())
        self.assertTrue(cif_count > 0)

    def test_one_cif2str(self):
        path = Path(
            "/Users/yuxing/projects/ar3l-search/example/summary_v2/Zn3Ni4(SbO6)2_900_240_Ni(OH)2_Sb2O3_ZnO_recipe138_f3ca1d77-a01d-4086-a8e8-2868b1719823/phases/target_phase.cif"
        )
        with TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            cif2str(path, tmpdir)
            self.assertTrue((tmpdir / f"{path.stem}.str").exists())
            print((tmpdir / f"{path.stem}.str").read_text())
