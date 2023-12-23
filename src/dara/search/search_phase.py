from pathlib import Path
from typing import Union


def search_phaes(
    pattern_path: Path, cif_paths: Union[list[Path], dict[Path, float]]
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
    ...
