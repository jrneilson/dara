"""Phase search module."""
from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

import jenkspy

from dara.search.tree import SearchTree

if TYPE_CHECKING:
    from pathlib import Path

    from dara.result import RefinementResult

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def remove_duplicate_results(
    results: dict[tuple[Path, ...], RefinementResult],
) -> dict[tuple[Path, ...], RefinementResult]:
    """
    Remove duplicate results.

    If two results have the same phases, only the one with the lower RWP will be kept.
    """
    results_ = {}
    appeared_phases = set()

    for phases, result in results.items():
        if set(phases) not in appeared_phases:
            results_[phases] = result
            appeared_phases.add(frozenset(phases))

    return results_


def search_phases(
    pattern_path: Path,
    cif_paths: list[Path],
    included_phases: list[Path] | None = None,
    max_phases: int = 3,
    top_n: int = 8,
    rpb_threshold: float = 1,
    return_search_tree: bool = False,
) -> dict[tuple[Path, ...], RefinementResult] | SearchTree:
    """Search for the best phases to use for refinement."""
    phase_params = {
        "gewicht": "0_0",
        "lattice_range": 0.01,
        "k1": "0_0^0.01",
        "k2": "fixed",
        "b1": "0_0^0.0025",
        "rp": 4,
    }
    refinement_params = {"n_threads": 8}

    # build the search tree
    search_tree = SearchTree(
        max_phases=max_phases,
        pattern_path=pattern_path,
        cif_paths=cif_paths,
        pinned_phases=included_phases,
        top_n=top_n,
        rpb_threshold=rpb_threshold,
        refine_params=refinement_params,
        phase_params=phase_params,
    )

    with ThreadPoolExecutor(max_workers=os.cpu_count() // top_n * 2 + 1) as executor:
        pending = {executor.submit(search_tree.expand_node, search_tree.root)}
        while pending:
            done = {f for f in pending if f.done()}
            pending = pending - done
            for future in done:
                if future.exception():
                    executor.shutdown(wait=False, cancel_futures=True)
                nodes = future.result()
                for node in nodes:
                    logger.info(f"Expanding node {node}")
                    pending.add(executor.submit(search_tree.expand_node, node))

    if not return_search_tree:
        results = search_tree.get_search_results()
        all_rhos = [result.lst_data.rho for result in results.values()]
        # get the first natural break
        if len(all_rhos) <= 5:
            return remove_duplicate_results(results)

        interval = jenkspy.jenks_breaks(all_rhos, n_classes=2)
        rho_cutoff = interval[1]
        results = {k: v for k, v in results.items() if v.lst_data.rho <= rho_cutoff}
        results = remove_duplicate_results(results)
        return results
    else:
        return search_tree
