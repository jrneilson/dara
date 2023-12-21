import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from dara.cif2str import cif2str
from spglib import get_error_message


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
            "/Users/yuxing/Downloads/CaGd2Zr(GaO3)4_orderings/CaGd2Zr(GaO3)4_ordering_20755.cif"
        )
        with TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            cif2str(path, tmpdir)
            self.assertTrue((tmpdir / f"{path.stem}.str").exists())
            print((tmpdir / f"{path.stem}.str").read_text())
