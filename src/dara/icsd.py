"""Interact with the (local) ICSD database."""
from __future__ import annotations

import itertools
import re
from pathlib import Path

from monty.serialization import loadfn
from pymatgen.analysis.structure_matcher import StructureMatcher
from pymatgen.core import Structure
from rxn_network.core import Composition
from rxn_network.utils.funcs import get_logger

from dara.utils import copy_and_rename_files

logger = get_logger(__name__)


class ICSDDatabase:
    """Class that represents the ICSD database. Note that the ICSD database is not publicly available, and you must have
    a local copy stored at the specified path.
    """

    def __init__(self, path_to_icsd):
        """
        Initialize the ICSD database.

        :param path_to_icsd: Path to the ICSD database
        """
        self.path_to_icsd = Path(path_to_icsd)
        self.icsd_dict = loadfn(Path(__file__).parent / "data/icsd_codes_by_chemsys.json.gz")

    def get_cifs_by_chemsys(self, chemsys, filter_unique=True, copy_files=True):
        """Get a list of ICSD codes corresponding to structures in a chemical system. Option to copy CIF files into a
        destination folder.
        """
        if isinstance(chemsys, str):
            elements = chemsys.split("-")

        elements_set = set(elements)  # remove duplicate elements
        all_icsd_codes = []
        all_formulas = []

        for i in range(len(elements_set)):
            for els in itertools.combinations(elements_set, i + 1):
                chemsys = "-".join(sorted(els))
                if chemsys in self.icsd_dict:
                    for formula, icsd_codes in self.icsd_dict[chemsys].items():
                        if filter_unique:
                            icsd_codes = [i["icsd_code"] for i in self.find_oldest_unique_structures(icsd_codes)]
                        all_icsd_codes.extend(icsd_codes)
                        all_formulas.extend([formula] * len(icsd_codes))

        if copy_files:
            copy_and_rename_files(
                self.path_to_icsd,
                f"{chemsys}",
                {f"{code}.cif": f"{formula}_{code}.cif" for formula, code in zip(all_formulas, all_icsd_codes)},
            )
        return all_icsd_codes

    def get_file_path(self, icsd_code: str | int):
        """Get the path to a CIF file in the ICSD database."""
        return self.path_to_icsd / f"{icsd_code}.cif"

    def get_codes_from_formula(self, formula: str, unique: bool = True):
        """Get a list of ICSD codes corresponding to a formula."""
        formula_reduced = Composition(formula).reduced_formula
        chemsys = Composition(formula).chemical_system
        icsd_chemsys = self.icsd_dict.get(chemsys)

        if not icsd_chemsys:
            logger.warning(f"No ICSD codes found for {formula}!")
            return []

        icsd_codes = icsd_chemsys.get(formula_reduced)
        if not icsd_codes:
            logger.warning(f"No ICSD codes found for {formula}!")
            return []

        return [i["icsd_code"] for i in self.find_oldest_unique_structures(icsd_codes)]

    def load_structure(self, icsd_code: str | int):
        """Load a pymatgen structure from a CIF file in the ICSD database."""
        return Structure.from_file(
            self.get_file_path(icsd_code).as_posix(),
            merge_tol=0.01,
            occupancy_tolerance=100,
        )

    def extract_year_from_cif(self, icsd_code: str | int):
        """Extract the year from a line in a CIF file that starts with 'primary' and contains a year.

        If the year is not found in the file, the function returns 10000.

        :param icsd_code: The ICSD code of the structure
        :return: The extracted year or a file not found error
        """
        file_path = self.get_file_path(icsd_code)

        try:
            with open(file_path) as file:
                for line in file:
                    # Match the specific pattern: 'primary' followed by a year
                    match = re.match(r"primary\s+.+(\d{4})\s.+", line)
                    if match:
                        # Return the year if a match is found
                        return int(match.group(1))
            return 10000
        except FileNotFoundError:
            return "File not found. Please check the file path."

    def find_oldest_unique_structures(self, icsd_codes: list[str | int]):
        """Get oldest uniques structures from a list of ICSD codes."""
        matcher = StructureMatcher()
        unique_structures: list[dict] = []

        for icsd_code in icsd_codes:
            struct = self.load_structure(icsd_code)

            year = self.extract_year_from_cif(icsd_code)
            new_data = {"icsd_code": icsd_code, "structure": struct, "year": year}

            is_duplicate = False
            for data in unique_structures:
                if matcher.fit(struct, data["structure"]):
                    is_duplicate = True
                    if year < data["year"]:
                        unique_structures.append(new_data)
                    break
            if not is_duplicate:
                unique_structures.append(new_data)

        return unique_structures
