"""APIs for running BGMN executable from Python."""

import os
from pathlib import Path
from subprocess import run


class BGMNWorker:
    """API for BGMN executable."""

    def __init__(self):
        self.bgmn_folder = (
            Path(__file__).parent.parent.parent / "bgmn" / "BGMNwin"
        ).absolute()

        self.bgmn_path = self.bgmn_folder / "bgmn"

        # Windows configuration
        if not self.bgmn_path.exists():
            self.bgmn_path = self.bgmn_folder / "bgmn.exe"

        if not self.bgmn_path.exists():
            raise FileNotFoundError("Cannot find BGMN executable.")

        os.environ["EFLECH"] = self.bgmn_folder.as_posix()
        os.environ["PATH"] += os.pathsep + self.bgmn_folder.as_posix()

    def run_refinement_cmd(self, control_file: Path, show_progress: bool = False):
        """
        Run refinement via BGMN executable.

        Args:
            control_file: the path to the control file (.sav)
            show_progress: whether to show the progress in the console
        """
        cp = run(
            [self.bgmn_path.as_posix(), control_file.absolute().as_posix()],
            cwd=control_file.parent.absolute().as_posix(),
            capture_output=not show_progress,
            check=False,
            timeout=600,
        )
        if cp.returncode:
            raise RuntimeError(
                f"Error in BGMN refinement for {control_file}. The exit code is {cp.returncode}\n"
                f"{cp.stdout}\n"
                f"{cp.stderr}"
            )
