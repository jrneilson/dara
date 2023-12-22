"""An interface for rxn_network and other engines for predicting products in a chemical reaction."""
from __future__ import annotations

import collections
import itertools
import logging
import math
import sys

from dara.phase_prediction.base import PredictionEngine
from dara.utils import get_chemsys_from_formulas, get_entry_by_formula, get_mp_entries
from pymatgen.core.composition import Element
from pymatgen.entries.computed_entries import ComputedStructureEntry
from rxn_network.core import Composition
from rxn_network.costs.calculators import (
    PrimaryCompetitionCalculator,
    SecondaryCompetitionCalculator,
)
from rxn_network.entries.entry_set import GibbsEntrySet
from rxn_network.enumerators.basic import BasicEnumerator, BasicOpenEnumerator
from rxn_network.enumerators.minimize import (
    MinimizeGibbsEnumerator,
    MinimizeGrandPotentialEnumerator,
)
from rxn_network.reactions.hull import InterfaceReactionHull
from rxn_network.reactions.reaction_set import ReactionSet

logger = logging.getLogger()
logging.basicConfig(level=logging.INFO, stream=sys.stdout)


class ReactionNetworkEngine(PredictionEngine):
    """Engine for predicting products in a chemical reaction."""

    def predict(
        precursors: list[str],
        temp: float,
        computed_entries: list[ComputedStructureEntry] | None = None,
        open_elem: str | None = None,
        chempot: float = 0,
        e_hull_cutoff: float = 0.05,
    ):
        """
        Predicts the intermediates/products of a mixture of precursors.

        Args:
            precursors: List of precursor formulas (no stoichiometry required)
            temp: Temperature in Kelvin
            computed_entries: Optional list of ComputedStructureEntry objects, otherwise
                will download from Materials Project using your MP_API key (must be stored
                in environment variables as $MP_API_KEY)
            open_elem: Optional open element (e.g., "O" for oxygen). If "O_air" is provided,
                will automatically default to oxygen with appropriate chemical potential
                (0.21 atm at desired temp).
            chempot: Optional chemical potential, defaults to 0 (standard state at the
                desired temp)
            e_hull_cutoff: Energy above hull cutoff by which to filter entries (default: takes
                all entries with an E_hull <= 50 meV/atom.)
        """
        precursors_comp = [Composition(p) for p in precursors]
        temp = round(temp)

        if computed_entries is None:
            computed_entries = get_mp_entries(get_chemsys_from_formulas([p.reduced_formula for p in precursors_comp]))

        gibbs = GibbsEntrySet.from_computed_entries(
            computed_entries,
            300,
            include_nist_data=True,  # acquire and filter entries at 300 K
        )
        gibbs = gibbs.filter_by_stability(e_hull_cutoff)
        gibbs = gibbs.get_entries_with_new_temperature(temp)

        if open_elem == "O_air":
            open_elem = "O"
            chempot = 0.5 * 8.617e-5 * temp * math.log(0.21)  # oxygen atmospheric partial pressure

        precursors_no_open = set(precursors_comp)

        if open_elem:
            precursors_no_open = precursors_no_open - {
                Composition(Composition(open_elem).reduced_formula)  # remove open element formula
            }

        precursors_no_open = list(precursors_no_open)

        reactants = [get_entry_by_formula(gibbs, r.reduced_formula) for r in precursors_comp]

        gibbs_entries_list = gibbs.entries_list
        for entry in reactants:
            if entry not in gibbs_entries_list:
                gibbs_entries_list.append(entry)
        gibbs = GibbsEntrySet(gibbs_entries_list)

        rxns = BasicEnumerator(precursors=precursors_no_open).enumerate(gibbs)

        rxns = rxns.add_rxn_set(MinimizeGibbsEnumerator(precursors=precursors_no_open).enumerate(gibbs))

        if open_elem:
            rxns = rxns.add_rxn_set(
                BasicOpenEnumerator(
                    [Composition(open_elem).reduced_formula],
                    precursors=precursors_no_open,
                ).enumerate(gibbs)
            )
            rxns = rxns.add_rxn_set(
                MinimizeGrandPotentialEnumerator(
                    open_elem=Element(open_elem),
                    mu=chempot,
                    precursors=precursors_no_open,
                ).enumerate(gibbs)
            )
            rxns = ReactionSet.from_rxns(rxns, rxns.entries, open_elem=open_elem, chempot=chempot)

        rxns = rxns.filter_duplicates()

        all_c1 = {}
        all_c2 = {}
        for combo in itertools.combinations(precursors_no_open, 2):
            combo = list(combo)
            if open_elem:
                combo.append(Composition(Composition(open_elem).reduced_formula))

            irh = InterfaceReactionHull(combo[0], combo[1], list(rxns.get_rxns_by_reactants(combo)))

            for r in irh.reactions:
                calc1 = PrimaryCompetitionCalculator(irh, temp)
                calc2 = SecondaryCompetitionCalculator(irh)

                c1 = calc1.calculate(r)
                c2 = calc2.calculate(r)

                for product in r.products:
                    if product in precursors_no_open:
                        continue
                    worse_c1 = False
                    worse_c2 = False

                    if product in all_c1 and c1 > all_c1[product]:
                        worse_c1 = True
                    if not worse_c1:
                        all_c1[product] = c1

                    if product in all_c2 and c2 > all_c2[product]:
                        worse_c2 = True
                    if not worse_c2:
                        all_c2[product] = c2

        all_c1 = collections.OrderedDict(sorted(all_c1.items(), key=lambda item: item[1]))
        all_c2 = collections.OrderedDict(sorted(all_c2.items(), key=lambda item: item[1]))

        return get_probabilities(all_c1, all_c2)


def get_probabilities(c1_data: dict, c2_data: dict, weights: tuple[float, float] = (0.5, 0.5)):
    """Convert primary and secondary competition values into net probability of appearance"""
    cost_rankings = []
    phases = []
    for phase in c1_data:
        c1 = c1_data[phase]
        c2 = c2_data[phase]

        cost = weights[0] * c1 + weights[1] * c2
        phases.append(phase)
        cost_rankings.append(cost)

    inverse_rankings = [1 / (cost - min(cost_rankings) + 1) for cost in cost_rankings]
    total_inverse_rankings = sum(inverse_rankings)
    probabilities = [inv_rank / total_inverse_rankings for inv_rank in inverse_rankings]
    return collections.OrderedDict(
        sorted(
            {k.reduced_formula: round(v, 4) for k, v in zip(phases, probabilities)}.items(),
            key=lambda item: item[1],
            reverse=True,
        )
    )
