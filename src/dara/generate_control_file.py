"""Generate a control file for BGMN."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from dara.utils import read_phase_name_from_str


def copy_instrument_files(instrument_name: str, working_dir: Path) -> None:
    """Copy the instrument files to the working directory."""
    instrument_path = Path(__file__).parent / "data" / "BGMN-Templates" / "Devices"

    for file in instrument_path.glob(f"{instrument_name}*"):
        shutil.copy(file, working_dir)


def copy_xy_pattern(pattern_path: Path, working_dir: Path) -> None:
    """Copy the xy pattern to the working directory."""
    shutil.copy(pattern_path, working_dir)


def generate_control_file(
    pattern_path: Path,
    str_paths: list[Path],
    instrument_name: str,
    working_dir: Path | None = None,
    *,
    n_threads: int = 8,
    wmin: float | None = None,
    wmax: float | None = None,
) -> Path:
    """Generate a control file for BGMN."""
    if working_dir is None:
        control_file_path = pattern_path.parent / f"{pattern_path.stem}.sav"
    else:
        control_file_path = working_dir / f"{pattern_path.stem}.sav"

    copy_xy_pattern(pattern_path, control_file_path.parent)
    copy_instrument_files(instrument_name, control_file_path.parent)

    phases_str = "\n".join(
        [f"STRUC[{i}]={str_path.name}" for i, str_path in enumerate(str_paths, start=1)]
    )

    phase_names = [read_phase_name_from_str(str_path) for str_path in str_paths]
    phase_fraction_str = "\n".join(
        [f"Q{phase_name}={phase_name}/sum" for phase_name in phase_names]
    )
    goal_str = "\n".join(
        [
            f"GOAL[{i}]=Q{phase_name}"
            for i, phase_name in enumerate(phase_names, start=1)
        ]
    )

    control_file = f"""
    % Theoretical instrumental function
    VERZERR={instrument_name}.geq
    % Wavelength
    LAMBDA=CU
    {f"WMIN={wmin}" if wmin is not None else ""}
    {f"WMAX={wmax}" if wmax is not None else ""}
    % Phases
    {phases_str}
    % Measured data
    VAL[1]={pattern_path.name}
    % Result list output
    LIST={pattern_path.stem}.lst
    % Peak list output
    OUTPUT={pattern_path.stem}.par
    % Diagram output
    DIAGRAMM={pattern_path.stem}.dia
    % Global parameters for zero point and sample displacement
    EPS1=0
    PARAM[1]=EPS2=0_-0.01^0.01
    NTHREADS={n_threads}
    PROTOKOLL=Y
    sum={"+".join(phase_name for phase_name in phase_names)}
    {phase_fraction_str}
    {goal_str}
    """
    control_file = re.sub(r"^\s+", "", control_file, flags=re.MULTILINE)

    with open(control_file_path, "w") as f:
        f.write(control_file)

    return control_file_path
