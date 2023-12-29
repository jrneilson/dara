from __future__ import annotations

from pathlib import Path

from dara import do_refinement_no_saving


def search_phases(
    pattern_path: Path,
    cif_paths: list[Path] | dict[Path, float],
    score_cutoff: float = 0.01,
) -> dict:
    """Search for the best phase for a given pattern.

    Args:
        pattern_path : Path to the pattern file.
        cif_paths : List[Path]
            List of paths to the cif files.

    Returns
    -------
        Dict
            A dictionary containing the search result.
    """
    if isinstance(cif_paths, list):
        cif_paths = {cif_path: 0 for cif_path in cif_paths}
    else:
        cif_paths = dict(sorted(cif_paths.items(), key=lambda x: x[1]))
        cif_paths = {k: v for k, v in cif_paths.items() if v <= score_cutoff}

    results = {}
    for cif_path in cif_paths:
        result = do_refinement_no_saving(pattern_path, [cif_path])

    return cif_paths
