import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ar3l_search.refine import do_refinement


class TestDoRefinement(unittest.TestCase):
    def test_do_refinement(self):
        folder = Path(__file__).parent.parent / "example" / "summary_v2"

        with TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            for pattern_folder in folder.glob("*"):
                if pattern_folder.is_dir():
                    pattern_path = list(pattern_folder.glob("*.xy"))[0]
                    cif_paths = list((pattern_folder / "phases").glob("*.cif"))
                    try:
                        result = do_refinement(
                            pattern_path, cif_paths, working_dir=tmpdir
                        )
                    except Exception as e:
                        print(f"Error in {pattern_path}")
                        raise e

                    self.assertTrue(
                        isinstance(result["Rwp"], float), msg=f"Error in {pattern_path}"
                    )

    def test_do_one_refinement(self):
        pattern_path = Path(
            "/Users/yuxing/projects/ar3l-search/example/CaGd2Zr(GaO3)4/MP350-pellet-24-33h.xy"
        )

        cif_paths = [pattern_path.parent / "target_phase.cif"]
        try:
            result = do_refinement(pattern_path, cif_paths)
        except Exception as e:
            print(f"Error in {pattern_path}")
            raise e

        print(result)
