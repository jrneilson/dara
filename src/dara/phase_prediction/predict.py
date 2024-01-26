"""Code for predicting products in a chemical reaction."""
from __future__ import annotations

import collections
import os
from pathlib import Path

from monty.json import MSONable
from rxn_network.core import Composition
from rxn_network.data import COMMON_GASES
from rxn_network.utils.funcs import get_logger

from dara.icsd import ICSDDatabase
from dara.utils import clean_icsd_code, copy_and_rename_files

logger = get_logger(__name__)


class PhasePredictor(MSONable):
    """Predict phases during solid-state synthesis."""

    def __init__(self, path_to_icsd, engine="reaction_network", **kwargs):
        """Initialize the engine."""
        if engine == "reaction_network":
            from dara.phase_prediction.rn import ReactionNetworkEngine

            self.engine = ReactionNetworkEngine(**kwargs)
            self.db = ICSDDatabase(path_to_icsd)

    def predict(
        self,
        precursors: list[str],
        temp: float = 1000,
        computed_entries=None,
        open_elem=None,
        chempot: float = 0.0,
        e_hull_cutoff=0.05,
    ) -> dict[str, float]:
        """Predict and rank the probability of appearance of products of a chemical reaction."""
        return self.engine.predict(
            precursors=precursors,
            temp=temp,
            computed_entries=computed_entries,
            open_elem=open_elem,
            chempot=chempot,
            e_hull_cutoff=e_hull_cutoff,
        )

    def write_cifs_from_formulas(
        self,
        prediction: dict,
        cost_cutoff: float = 0.025,
        e_hull_filter: float = 0.1,
        dest_dir: str = "cifs",
        exclude_gases: bool = True,
    ):
        """Write CIFs of the predicted products."""
        prediction_sorted = collections.OrderedDict(sorted(prediction.items(), key=lambda item: item[1]))
        dest_dir = Path(dest_dir)
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)

        for idx, (f, cost) in enumerate(prediction_sorted.items()):
            if cost > cost_cutoff:
                logger.info("Reached cost cutoff.")
                break

            formula = Composition(f).reduced_formula

            if exclude_gases and formula in COMMON_GASES:
                logger.info("Skipping common gas: %s", formula)
                continue

            icsd_data = self.db.get_formula_data(formula)
            if not icsd_data:
                continue

            file_map = {}
            for formula, code, sg, e_hull in icsd_data:
                if e_hull is not None and e_hull > e_hull_filter:
                    print(f"Skipping high-energy phase: {code} ({formula}, {sg}): e_hull = {e_hull}")
                    continue

                e_hull_value = round(1000 * e_hull) if e_hull is not None else None
                file_map[f"icsd_{clean_icsd_code(code)}.cif"] = f"{formula}_{sg}_({code})-{e_hull_value}.cif"

            copy_and_rename_files(self.db.path_to_icsd, dest_dir, file_map)
