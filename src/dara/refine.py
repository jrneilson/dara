"""Perform refinements with BGMN."""
from __future__ import annotations

import tempfile
from pathlib import Path

from dara.bgmn_worker import BGMNWorker
from dara.cif2str import cif2str
from dara.generate_control_file import generate_control_file
from dara.result import get_result
from dara.xrdml2xy import xrdml2xy


def do_refinement(
    pattern_path: Path,
    cif_paths: list[Path],
    instrument_name: str = "Aeris-fds-Pixcel1d-Medipix3",
    working_dir: Path | None = None,
    phase_params: dict | None = None,
    refinement_params: dict | None = None,
    show_progress: bool = False,
):
    """Refine the structure using BGMN."""
    if working_dir is None:
        working_dir = pattern_path.parent / f"refinement_{pattern_path.stem}"

    if not working_dir.exists():
        working_dir.mkdir(exist_ok=True, parents=True)

    if phase_params is None:
        phase_params = {}

    if refinement_params is None:
        refinement_params = {}

    if pattern_path.suffix == ".xrdml":
        pattern_path = xrdml2xy(pattern_path, working_dir)

    str_paths = []
    for cif_path in cif_paths:
        str_path = cif2str(cif_path, working_dir, **phase_params)
        str_paths.append(str_path)

    control_file_path = generate_control_file(
        pattern_path,
        str_paths,
        instrument_name,
        working_dir=working_dir,
        **refinement_params,
    )

    bgmn_worker = BGMNWorker()
    bgmn_worker.run_refinement_cmd(control_file_path, show_progress=show_progress)
    return get_result(control_file_path)


def do_refinement_no_saving(
    pattern_path: Path,
    cif_paths: list[Path],
    instrument_name: str = "Aeris-fds-Pixcel1d-Medipix3",
    phase_params: dict | None = None,
    refinement_params: dict | None = None,
    show_progress: bool = False,
):
    """Refine the structure using BGMN in a temporary directory without saving."""
    with tempfile.TemporaryDirectory() as tmpdir:
        working_dir = Path(tmpdir)

        return do_refinement(
            pattern_path,
            cif_paths,
            instrument_name,
            working_dir=working_dir,
            phase_params=phase_params,
            refinement_params=refinement_params,
            show_progress=show_progress,
        )
