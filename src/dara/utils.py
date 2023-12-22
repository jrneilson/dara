"""Utility functions for the dara package."""
import os
import re
import shutil
from pathlib import Path

from rxn_network.core import Composition
from rxn_network.entries.entry_set import GibbsEntrySet
from rxn_network.utils.funcs import get_logger

logger = get_logger(__name__)

with open(Path(__file__).parent / "data" / "possible_species.txt") as f:
    POSSIBLE_SPECIES = {sp.strip() for sp in f}


def process_phase_name(phase_name: str) -> str:
    """Process the phase name to remove special characters."""
    return re.sub(r"[\s_/\\+–*]", "", phase_name)


def bool2yn(value: bool) -> str:
    """Convert boolean to Y (yes) or N (no)."""
    return "Y" if value else "N"


def read_phase_name_from_str(str_path: Path) -> str:
    """Get the phase name from the str file path.

    Example of str:
    PHASE=BaSnO3 // generated from pymatgen
    FORMULA=BaSnO3 //
    Lattice=Cubic HermannMauguin=P4/m-32/m Setting=1 SpacegroupNo=221 //
    PARAM=A=0.41168_0.40756^0.41580 //
    RP=4 PARAM=k1=0_0^1 k2=0 PARAM=B1=0_0^0.01 PARAM=GEWICHT=0_0 //
    GOAL:BaSnO3=GEWICHT //
    GOAL=GrainSize(1,1,1) //
    E=BA+2 Wyckoff=b x=0.500000 y=0.500000 z=0.500000 TDS=0.010000
    E=SN+4 Wyckoff=a x=0.000000 y=0.000000 z=0.000000 TDS=0.010000
    E=O-2 Wyckoff=d x=0.000000 y=0.000000 z=0.500000 TDS=0.010000
    """
    text = str_path.read_text()
    return re.search(r"PHASE=(\w*)", text).group(1)


def standardize_coords(x, y, z):
    # Adjust coordinates to specific fractional values if close
    fractions = {
        0.3333: 1 / 3,
        0.6667: 2 / 3,
        0.1667: 1 / 6,
        0.8333: 5 / 6,
        0.0833: 1 / 12,
        0.4167: 5 / 12,
        0.5833: 7 / 12,
        0.9167: 11 / 12,
    }

    for key, value in fractions.items():
        if abs(x - key) < 0.0001:
            x = value
        if abs(y - key) < 0.0001:
            y = value
        if abs(z - key) < 0.0001:
            z = value

    return x, y, z


def fuzzy_compare(a: float, b: float):
    fa = round(a, 6)
    fb = round(b, 6)

    # Normalizing the fractional parts to be within [0, 1]
    while fa < 0.0:
        fa += 1.0
    while fb < 0.0:
        fb += 1.0
    while fa > 1.0:
        fa -= 1.0
    while fb > 1.0:
        fb -= 1.0

    # Checking specific fractional values
    fractions = [
        (0.3333, 0.3334),  # 1/3
        (0.6666, 0.6667),  # 2/3
        (0.1666, 0.1667),  # 1/6
        (0.8333, 0.8334),  # 5/6
        (0.0833, 0.0834),  # 1/12
        (0.4166, 0.4167),  # 5/12
        (0.5833, 0.5834),  # 7/12
        (0.9166, 0.9167),  # 11/12
    ]

    for lower, upper in fractions:
        if lower <= fa <= upper and lower <= fb <= upper:
            return True

    # Fuzzy comparison for general case
    def is_close(_a, _b, rel_tol=1e-09, abs_tol=1e-6):
        # Custom implementation of fuzzy comparison
        return abs(_a - _b) <= max(rel_tol * max(abs(_a), abs(_b)), abs_tol)

    return is_close(fa, fb)


def copy_and_rename_files(src_directory, dest_directory, file_map):
    """Copy specific files from the source directory to the destination directory with new names.

    :param src_directory: Path to the source directory
    :param dest_directory: Path to the destination directory
    :param file_map: Dictionary where keys are original filenames and values are new filenames
    """
    # Ensure the destination directory exists
    if not os.path.exists(dest_directory):
        os.makedirs(dest_directory)

    # Copy and rename each specified file
    for src_filename, dest_filename in file_map.items():
        src_file = os.path.join(src_directory, src_filename)
        dest_file = os.path.join(dest_directory, dest_filename)

        # Check if file exists and is a file (not a directory)
        if os.path.isfile(src_file):
            shutil.copy(src_file, dest_file)
            print(f"Copied {src_filename} to {dest_filename} in {dest_directory}")
        else:
            print(f"File {src_filename} not found in {src_directory}")


def get_entry_by_formula(gibbs_entries: GibbsEntrySet, formula: str):
    """Either returns the minimum energy entry or a new interpolated entry."""
    try:
        entry = gibbs_entries.get_min_entry_by_formula(formula)
    except:
        entry = gibbs_entries.get_interpolated_entry(formula)  # if entry is missing, use interpolated one
    return entry


def get_chemsys_from_formulas(formulas: list[str]):
    """Convert a list of formulas to a chemsys."""
    elements = set()
    for formula in formulas:
        elements.update(Composition(formula).elements)

    return "-".join(sorted([str(e) for e in elements]))


def get_mp_entries(chemsys: str):
    """Download ComputedStructureEntry objects from Materials Project."""
    logger.info("Downloading entries from Materials Project...")
    from mp_api.client import MPRester

    with MPRester() as mpr:
        return mpr.get_entries_in_chemsys(chemsys)
