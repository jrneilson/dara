"""Interact with the (local) ICSD database."""
from __future__ import annotations

import itertools
from pathlib import Path

from monty.serialization import loadfn
from rxn_network.core import Composition
from rxn_network.utils.funcs import clean_icsd_code, get_logger

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
        self.icsd_dict = loadfn(Path(__file__).parent / "data/icsd_filtered_info_2024.json.gz")

    def get_cifs_by_chemsys(self, chemsys, e_hull_filter=0.2, copy_files=True):
        """Get a list of ICSD codes corresponding to structures in a chemical system. Option to copy CIF files into a
        destination folder.
        """
        if isinstance(chemsys, str):
            elements = chemsys.split("-")

        elements_set = set(elements)  # remove duplicate elements
        all_data = []

        for i in range(len(elements_set)):
            for els in itertools.combinations(elements_set, i + 1):
                chemsys = "-".join(sorted(els))
                if chemsys in self.icsd_dict:
                    all_data.extend(self.icsd_dict[chemsys])

        file_map = {}
        for formula, code, sg, e_hull in all_data:
            if e_hull is not None and e_hull > e_hull_filter:
                print(f"Skipping high-energy phase: {code} ({formula}, {sg}): e_hull = {e_hull}")
                continue

            e_hull_value = round(1000 * e_hull) if e_hull is not None else None
            file_map[f"icsd_{clean_icsd_code(code)}.cif"] = f"{formula}_{sg}_({code})-{e_hull_value}.cif"

        if copy_files:
            copy_and_rename_files(self.path_to_icsd, f"{chemsys}", file_map)

        return [data[1] for data in all_data]

    def get_file_path(self, icsd_code: str | int):
        """Get the path to a CIF file in the ICSD database."""
        return self.path_to_icsd / f"icsd_{clean_icsd_code(icsd_code)}.cif"

    def get_formula_data(self, formula: str):
        """Get a list of ICSD codes corresponding to a formula."""
        formula_reduced = Composition(formula).reduced_formula
        chemsys = Composition(formula).chemical_system
        icsd_chemsys = self.icsd_dict.get(chemsys)

        if not icsd_chemsys:
            logger.warning(f"No ICSD codes found in chemical system: {icsd_chemsys}!")
            return []

        formula_data = [i for i in icsd_chemsys if i[0] == formula_reduced]
        if not formula_data:
            logger.warning(f"No ICSD codes found for {formula}!")
            return []

        return formula_data
