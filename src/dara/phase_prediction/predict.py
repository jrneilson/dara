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
from dara.phase_prediction.structure import clean_cifs
from dara.utils import copy_and_rename_files

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
        precursors,
        temp=1000,
        computed_entries=None,
        open_elem=None,
        chempot=0.0,
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
        self, prediction, cost_cutoff=0.01, dest_dir="cifs", clean=True, unique=True, exclude_gases=True
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

            icsd_data = self.db.get_formula_data(formula, unique=unique)
            if not icsd_data:
                continue

            copy_and_rename_files(
                self.db.path_to_icsd,
                dest_dir,
                {f"{data['icsd_code']}.cif": f"{idx}_{formula}_{data['icsd_code']}.cif" for data in icsd_data},
            )

        if clean:
            clean_cifs(dest_dir, str(dest_dir) + "_cleaned")
