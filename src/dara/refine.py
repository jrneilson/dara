"""Perform refinements with BGMN."""
import tempfile
from pathlib import Path
from typing import List, Optional

from dara.bgmn_worker import BGMNWorker
from dara.cif2str import cif2str
from dara.generate_control_file import generate_control_file
from dara.results import get_result
from dara.xrdml2xy import xrdml2xy


def do_refinement(
    pattern_path: Path,
    cif_paths: List[Path],
    instrument_name: str = "Aeris-fds-Pixcel1d-Medipix3",
    working_dir: Optional[Path] = None,
    **refinement_params,
):
    """Refine the structure using BGMN."""
    if working_dir is None:
        working_dir = pattern_path.parent / f"refinement_{pattern_path.stem}"

    if not working_dir.exists():
        working_dir.mkdir(exist_ok=True, parents=True)

    if pattern_path.suffix == ".xrdml":
        pattern_path = xrdml2xy(pattern_path, working_dir)

    str_paths = []
    for cif_path in cif_paths:
        str_path = cif2str(cif_path, working_dir)
        str_paths.append(str_path)

    control_file_path = generate_control_file(
        pattern_path,
        str_paths,
        instrument_name,
        working_dir=working_dir,
        **refinement_params,
    )

    bgmn_worker = BGMNWorker()
    bgmn_worker.run_refinement_cmd(control_file_path)
    result = get_result(control_file_path)

    return result


def do_refinement_no_saving(
    pattern_path: Path,
    cif_paths: List[Path],
    instrument_name: str = "Aeris-fds-Pixcel1d-Medipix3",
    **refinement_params,
):
    """Refine the structure using BGMN in a temporary directory without saving"""
    with tempfile.TemporaryDirectory() as tmpdir:
        working_dir = Path(tmpdir)

        result = do_refinement(
            pattern_path,
            cif_paths,
            instrument_name,
            working_dir=working_dir,
            **refinement_params,
        )

    return result
