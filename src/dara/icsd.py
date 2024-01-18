"""Interact with the (local) ICSD database."""
from __future__ import annotations

import itertools
import os
from pathlib import Path

from monty.serialization import loadfn
from pymatgen.analysis.structure_analyzer import SpacegroupAnalyzer
from pymatgen.analysis.structure_matcher import StructureMatcher
from pymatgen.core import Structure
from rxn_network.core import Composition
from rxn_network.utils.funcs import get_logger
from tqdm import tqdm

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
        self.icsd_dict = loadfn(Path(__file__).parent / "data/icsd_filtered_info_2019.json.gz")

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
            file_map[f"{code}.cif"] = f"{formula}_{sg}_({code}),{e_hull_value}.cif"

        if copy_files:
            copy_and_rename_files(self.path_to_icsd, f"{chemsys}", file_map)

        return [data[1] for data in all_data]

    def get_file_path(self, icsd_code: str | int):
        """Get the path to a CIF file in the ICSD database."""
        return self.path_to_icsd / f"{icsd_code}.cif"

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

    def load_structure(self, icsd_code: str | int):
        """Load a pymatgen structure from a CIF file in the ICSD database."""
        return Structure.from_file(
            self.get_file_path(icsd_code).as_posix(),
            merge_tol=0.01,
            occupancy_tolerance=100,
        )


class ICSDParser:
    """Class that parses the ICSD database.

    NOTE: this class is used offline to create data/icsd_filtered_info_2019.json.gz and is not tested for general use.
    """

    def __init__(self, icsd_directory, icsd_data=None):
        self.icsd_directory = Path(icsd_directory)
        self._icsd_data = icsd_data  # provide, or call load_structures_and_metadata() to populate

        # (lowest) e-hulls and corresponding spacegroup info of MP structures, precomputed, and sorted by formula:
        self.mp_struct_info = loadfn(Path(__file__).parent / "data/mp_struct_info.json.gz")

    def parse(self):
        """Parse all CIFs in the supplied ICSD directory."""
        if self._icsd_data is None:
            self.load_structures_and_metadata()

        filtered_data = {}
        for chemsys, all_data in tqdm(list(self._icsd_data.items()), desc="Filtering/prioritizing structures..."):
            # self._icsd_data[chemsys] = sorted(all_data, key=lambda x: x["date"])
            grouped_data = self._group_structures(all_data)
            for group in grouped_data:
                group_sorted = sorted(group, key=lambda x: (abs(x["temp"] - 293.0), x["date"]))
                selected = group_sorted[0]
                sg = selected["structure"].get_space_group_info(symprec=0.1)[1]
                formula = selected["structure"].composition.reduced_formula
                data = [formula, selected["icsd_id"], sg, None]

                if formula in self.mp_struct_info:
                    for e_hull, mp_sg in self.mp_struct_info[formula]:
                        if sg == mp_sg[1]:  # exact structure matching too imprecise
                            data[3] = e_hull  # always gets lowest e_hull of match
                            break

                if chemsys in filtered_data:
                    filtered_data[chemsys].append(tuple(data))
                else:
                    filtered_data[chemsys] = [tuple(data)]

        return filtered_data

    def load_structures_and_metadata(self):
        """Load a dictionary of structures and metadata from the ICSD directory.
        The dict is sorted by chemical system.
        """
        struct_data = {}
        for filename in tqdm(sorted(os.listdir(self.icsd_directory)), desc="Loading ICSD structures..."):
            file_path = self.icsd_directory / filename
            if file_path.suffix != ".cif":
                continue

            struct = self.load_structure_from_cif(filename)
            if struct is None:
                print("Error loading CIF. Skipping file:", filename)
                continue

            metadata = self.get_metadata_from_cif(filename)
            data = {"structure": struct, **metadata}

            chemsys = struct.composition.chemical_system

            if chemsys in struct_data:
                struct_data[chemsys].append(data)
            else:
                struct_data[chemsys] = [data]

        self._icsd_data = struct_data

        return struct_data

    def load_structure_from_cif(self, filename):
        """
        Load a CIF file into a pymatgen structure object.

        Args:
            filename: filename of CIF to be loaded
        Returns:
            structure: pymatgen structure object
        """
        structure = None

        try:
            refined_structure = SpacegroupAnalyzer(
                Structure.from_file(self.icsd_directory / filename, site_tolerance=1e-3)
            ).get_refined_structure()
            structure = SpacegroupAnalyzer(refined_structure).get_symmetrized_structure()
        except Exception:
            pass

        return structure

    def get_metadata_from_cif(self, filename):
        """
        Parse the metadata from a CIF file.

        Args:
            filename: filename of CIF to be parsed
        """
        metadata = {}
        icsd_id, date, temp = None, None, 0  # default temperature is 0 K, required for sorting
        with open(self.icsd_directory / filename) as entry:
            for line in entry.readlines():
                if "_database_code_ICSD" in line:
                    icsd_id = int(line.split()[-1])
                if "_audit_creation_date" in line:
                    date = line.split()[-1]
                if "_cell_measurement_temperature" in line:
                    temp = float(line.split()[-1])

        metadata["icsd_id"] = icsd_id
        metadata["date"] = date
        metadata["temp"] = temp

        return metadata

    def _group_structures(self, data, max_multiple=12, **kwargs):
        """Group structures by structural similarity."""
        sorted_data = []
        matcher = StructureMatcher(**kwargs)

        # pre-sort by spacegroup to speed up matching
        grouped_structures = {}
        for item in data:
            reduced_comp = item["structure"].composition.reduced_composition
            if len(item["structure"]) > max_multiple * reduced_comp.num_atoms:
                print("skipping (too big):", item["icsd_id"])
                continue
            try:
                analyzer = SpacegroupAnalyzer(structure=item["structure"], symprec=0.1)
                sg_data = analyzer._space_group_data
            except Exception as e:
                print("Error: Excluding ICSD ID", item["icsd_id"], e)
                continue

            if sg_data is None:
                print("No data: Excluding ICSD ID", item["icsd_id"])
                continue

            sg = sg_data["number"]

            if sg in grouped_structures:
                grouped_structures[sg].append(item)
            else:
                grouped_structures[sg] = [item]

        for items in grouped_structures.values():
            grouped_structures_sg = {}
            for item in items:
                structure = item["structure"]
                added = False
                for key in grouped_structures_sg:
                    if matcher.fit(structure, grouped_structures_sg[key][0]["structure"]):
                        grouped_structures_sg[key].append(item)
                        added = True
                        break
                if not added:
                    grouped_structures_sg[len(grouped_structures_sg)] = [item]
            sorted_data.extend(list(grouped_structures_sg.values()))

        return sorted_data

    @property
    def icsd_data(self):
        return self._icsd_data
