"""A script to filter and group the cod, removing duplicate structures and classifying
symmetry.
"""

import logging
from pathlib import Path

from monty.serialization import dumpfn, loadfn
from pymatgen.analysis.structure_analyzer import SpacegroupAnalyzer
from pymatgen.analysis.structure_matcher import StructureMatcher
from tqdm import tqdm

from dara.cif import Cif

# path_to_cod = Path(SETTINGS.PATH_TO_COD)
path_to_cod = Path("/Users/mcdermott/COD_test")
MAX_NUM_ATOMS = 128


def load_cod_structures():
    """Load COD structures and metadata. Groups by chemical system.

    This assumes you have a COD_2024 folder acquired through the standard rsync approach:
        rsync -av --delete rsync://www.crystallography.net/cif/ COD_2024/

    Note that this folder will probably include two levels of sub folders (e.g.
    COD_2024/7/03/03/...). This will not affect parsing.

    See DaraSettings for the default path or to configure with a dara.yaml file.
    """
    cod_data = {}

    for filename in tqdm(sorted(path_to_cod.rglob("*.cif")), desc="Loading COD structures..."):
        try:
            cif = Cif.from_file(filename)
        except Exception as err:
            logging.error(f"Error reading CIF from file: {filename} due to error: {err}")
            continue

        try:
            structure = cif.to_structure(merge_tol=0.01, occupancy_tolerance=100)
        except Exception:
            logging.error(f"Error parsing CIF from file: {filename}. Skipping...")
            continue

        metadata = cif.data[next(iter(cif.data.keys()))].data

        date = metadata.get("_journal_year", None)
        temp = float(str(metadata.get("_diffrn_ambient_temperature", 0)).split("(", maxsplit=1)[0])
        if temp == 0:
            temp = float(str(metadata.get("_cell_measurement_temperature", 0)).split("(", maxsplit=1)[0])
        cod_id = str(metadata.get("_cod_database_code", filename.stem))  # prefer whats in CIF
        data = {"structure": structure, "temp": temp, "date": date, "cod_id": cod_id}

        chemsys = structure.composition.chemical_system

        if chemsys in cod_data:
            cod_data[chemsys].append(data)
        else:
            cod_data[chemsys] = [data]

    return cod_data


def filter_cod_structures(cod_data, mp_struct_info):
    """Filter and prioritize COD structures based on space group and MP data.

    Specifically:

    1) Remove duplicate structures using StructureMatcher
    2) Remove structures that are too big (>128 atoms)
    3) Prioritize structures based on proximity to room temperature
    4) Associate MP data (formation energy, space group) with COD data
    """
    filtered_data = {}

    for chemsys, data in tqdm(list(cod_data.items()), desc="Filtering structures..."):
        matcher = StructureMatcher(allow_subset=True)

        # pre-sort by spacegroup to speed up matching
        grouped_structures = {}
        for item in data:
            if len(item["structure"]) > MAX_NUM_ATOMS:
                print("skipping (too big):", item["cod_id"])
                continue
            try:
                sg_data = SpacegroupAnalyzer(structure=item["structure"], symprec=0.1)._space_group_data
            except Exception:
                sg_data = None

            if sg_data is None:
                try:  # different tolerance
                    sg_data = SpacegroupAnalyzer(structure=item["structure"], symprec=0.01)._space_group_data
                except Exception:
                    try:
                        sg_data = SpacegroupAnalyzer(
                            structure=item["structure"], symprec=0.01, angle_tolerance=10
                        )._space_group_data
                    except Exception:
                        print("No symmetry data for cod ID", item["cod_id"])
                        continue

            if sg_data is None:
                print("No data: Excluding cod ID", item["cod_id"])
                continue

            sg = sg_data["number"]

            if sg in grouped_structures:
                grouped_structures[sg].append(item)
            else:
                grouped_structures[sg] = [item]

        # group matched structures for downstream filteering
        sorted_data = []
        for sg, group in grouped_structures.items():
            grouped_structures_sg = {}
            for item in group:
                structure = item["structure"]
                added = False

                for k, v in grouped_structures_sg.items():
                    if matcher.fit(structure, v[0]["structure"]):
                        grouped_structures_sg[k].append(item)
                        added = True
                        break

                if not added:
                    grouped_structures_sg[len(grouped_structures_sg)] = [item]

            sorted_data.append((sg, list(grouped_structures_sg.values())))

        for sg, groups in sorted_data:
            for group in groups:
                group_sorted = sorted(group, key=lambda x: (abs(x["temp"] - 293.0), x["date"]))
                selected = group_sorted[0]
                formula = selected["structure"].composition.reduced_formula
                data = [formula, selected["cod_id"], sg, None]

                if formula in mp_struct_info:
                    for e_hull, mp_sg in mp_struct_info[formula]:
                        if sg == mp_sg[1]:  # exact structure matching too imprecise
                            data[3] = e_hull  # always gets lowest e_hull of match
                            break

                if chemsys in filtered_data:
                    filtered_data[chemsys].append(tuple(data))
                else:
                    filtered_data[chemsys] = [tuple(data)]

    return filtered_data


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    path = Path(__file__).resolve()

    logging.info("Loading information on MP structures (formulas, space groups, e_hulls)...")
    mp_struct_info = loadfn(Path(__file__).resolve().parent.parent / "src/dara/data/mp_struct_info.json.gz")

    logging.info("Loading COD structures...")
    cod_data = load_cod_structures()

    filtered_data = filter_cod_structures(cod_data, mp_struct_info)

    logging.info("Saving filtered COD data...")

    dumpfn(filtered_data, "cod_filtered_info_2024.json.gz")
