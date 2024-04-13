"""Interact with the (local) ICSD database."""

from __future__ import annotations

import itertools
from pathlib import Path

from monty.serialization import loadfn
from pymatgen.core import Composition

from dara import SETTINGS
from dara.data import COMMON_GASES
from dara.utils import clean_icsd_code, copy_and_rename_files, get_logger

logger = get_logger(__name__)


class ICSDDatabase:
    """Class that represents the ICSD database.

    WARNING: the ICSD database is not publicly available, and you must have a local copy
    stored at the specified path. The default path is set in SETTINGS.PATH_TO_ICSD.
    """

    def __init__(self, path_to_icsd: str | None = None):
        """
        Initialize the ICSD database.

        :param path_to_icsd: Path to the ICSD database
        """
        self.path_to_icsd = path_to_icsd
        self.icsd_dict = loadfn(Path(__file__).parent / "data/icsd_filtered_info_2024_v2.json.gz")

    def get_cifs_by_formulas(
        self,
        formulas: list[str],
        e_hull_filter: float = 0.1,
        copy_files=True,
        dest_dir: str = "cifs",
        exclude_gases: bool = True,
    ):
        """Get a list of ICSD codes corresponding to formulas, and optionally copy CIF
        files into a destination folder.
        """
        file_map = {}
        all_data = []
        for formula in formulas:
            all_data.extend(self.get_formula_data(formula))

        file_map = self._generate_file_map(all_data, e_hull_filter, exclude_gases)

        if copy_files:
            copy_and_rename_files(self.icsd_path, dest_dir, file_map)

        return [data[1] for data in all_data]

    def get_cifs_by_chemsys(
        self,
        chemsys: str | list[str] | set[str],
        e_hull_filter: float = 0.1,
        copy_files=True,
        dest_dir: str = "cifs",
        exclude_gases: bool = True,
    ):
        """Get a list of ICSD codes corresponding to structures in a chemical system.
        Option to copy CIF files into a destination folder.
        """
        if isinstance(chemsys, str):
            chemsys = chemsys.split("-")

        elements_set = set(chemsys)  # remove duplicate elements
        all_data = []

        for i in range(len(elements_set)):
            for els in itertools.combinations(elements_set, i + 1):
                sub_chemsys = "-".join(sorted(els))
                if sub_chemsys in self.icsd_dict:
                    all_data.extend(self.icsd_dict[sub_chemsys])

        file_map = self._generate_file_map(all_data, e_hull_filter, exclude_gases)

        if copy_files:
            copy_and_rename_files(self.icsd_path, dest_dir, file_map)

        return [data[1] for data in all_data]

    def get_file_path(self, icsd_code: str | int):
        """Get the path to a CIF file in the ICSD database."""
        return self.icsd_path / f"icsd_{clean_icsd_code(icsd_code)}.cif"

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

    @property
    def icsd_path(self):
        """Path to the ICSD database. Automatically uses the default path if not
        provided.
        """
        path = SETTINGS.PATH_TO_ICSD
        if self.path_to_icsd is not None:
            path = self.path_to_icsd

        return Path(path)

    def _generate_file_map(self, all_data, e_hull_filter, exclude_gases):
        file_map = {}
        for formula, code, sg, e_hull in all_data:
            if exclude_gases and formula in COMMON_GASES:
                logger.info("Skipping common gas: %s", formula)
                continue

            if e_hull is not None and e_hull > e_hull_filter:
                print(f"Skipping high-energy phase: {code} ({formula}, {sg}): e_hull = {e_hull}")
                continue

            e_hull_value = round(1000 * e_hull) if e_hull is not None else None
            file_map[f"icsd_{clean_icsd_code(code)}.cif"] = f"{formula}_{sg}_({code})-{e_hull_value}.cif"

        return file_map
