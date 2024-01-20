from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import jenkspy
import numpy as np
import ray
from pymatgen.core import Structure
from sklearn.cluster import AgglomerativeClustering

from dara import do_refinement_no_saving
from dara.eflech_worker import EflechWorker
from dara.result import RefinementResult
from dara.search.peak_matcher import PeakMatcher
from dara.utils import get_number, rpb

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def get_best_phase(
    peak_matchers: dict[Path, PeakMatcher], top_n: int = 10
) -> list[Path]:
    return sorted(peak_matchers, key=lambda x: peak_matchers[x].score(), reverse=True)[
        :top_n
    ]


@ray.remote(num_cpus=1)
def _remote_do_refinement_no_saving(
    pattern_path: Path,
    cif_paths: list[Path],
    instrument_name: str = "Aeris-fds-Pixcel1d-Medipix3",
    phase_params: dict[str, Any] | None = None,
    refinement_params: dict[str, float] | None = None,
) -> RefinementResult:
    result = do_refinement_no_saving(
        pattern_path,
        cif_paths,
        instrument_name=instrument_name,
        phase_params=phase_params,
        refinement_params=refinement_params,
    )
    return result


def batch_refine(
    pattern_path: Path,
    all_cif_paths: list[list[Path]],
) -> list[RefinementResult]:
    handles = [
        _remote_do_refinement_no_saving.remote(
            pattern_path,
            cif_paths,
            refinement_params={"wmin": 10, "wmax": 60},
            phase_params={
                "gewicht": "0_0",
                "k1": "0_0^0.01",
                "k2": "0_0^0.01",
                "b1": "0_0^0.01",
                "rp": 4,
            },
        )
        for cif_paths in all_cif_paths
    ]
    return ray.get(handles)


def fom(phase_path: Path, result: RefinementResult) -> float:
    a = b = c = d = 1.0
    b1_threshold = 2e-2
    k2_threshold = 1e-5

    initial_lattice_abc = Structure.from_file(phase_path.as_posix()).lattice.abc

    refined_a = result.lst_data.phases_results[phase_path.stem].a
    refined_b = result.lst_data.phases_results[phase_path.stem].b
    refined_c = result.lst_data.phases_results[phase_path.stem].c

    refined_lattice_abc = [
        refined_a,
        refined_b if refined_b is not None else refined_a,
        refined_c if refined_c is not None else refined_a,
    ]
    refined_lattice_abc = [get_number(x) for x in refined_lattice_abc]

    initial_lattice_abc = np.array(initial_lattice_abc) / 10  # convert to nm
    refined_lattice_abc = np.array(refined_lattice_abc)

    delta_u = (
        np.sum(np.abs(initial_lattice_abc - refined_lattice_abc) / initial_lattice_abc)
        * 100
    )

    if delta_u <= 1:
        a = 0

    geweicht = result.lst_data.phases_results[phase_path.stem].gewicht
    geweicht = get_number(geweicht)

    b1 = get_number(result.lst_data.phases_results[phase_path.stem].B1)
    k2 = get_number(result.lst_data.phases_results[phase_path.stem].k2)

    if b1 is None or b1 < b1_threshold:
        c = 0
    else:
        c /= b1
    if k2 is None or k2 < k2_threshold:
        d = 0
    else:
        d *= k2

    return (1 / (result.lst_data.rwp + a * delta_u + 1e-4) + b * geweicht) / (1 + c + d)


def similarity_score(peaks1: np.ndarray, peaks2: np.ndarray) -> float:
    pm = PeakMatcher(peaks1, peaks2)
    return 1 - pm.jaccard_index()


def group_phases(
    phases: dict[Path, RefinementResult], distance_threshold: float = 0.1
) -> list[dict[Path, RefinementResult]]:
    peaks = []

    for phase, result in phases.items():
        all_peaks = result.peak_data
        peaks.append(
            all_peaks[all_peaks["phase"] == phase.stem][["2theta", "intensity"]].values
        )

    # get distance matrix
    distance_matrix = np.zeros((len(phases), len(phases)))

    for i in range(len(phases)):
        for j in range(len(phases)):
            distance_matrix[i, j] = similarity_score(peaks[i], peaks[j])

    # current peak matching algorithm is not a symmetric metric.
    distance_matrix = (distance_matrix + distance_matrix.T) / 2

    # clustering
    clusterer = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=distance_threshold,
        metric="precomputed",
        linkage="average",
    )
    clusterer.fit(distance_matrix)

    clusters = {}
    for i, cluster in enumerate(clusterer.labels_):
        if cluster not in clusters:
            clusters[cluster] = {}
        clusters[cluster][list(phases.keys())[i]] = list(phases.values())[i]

    return list(clusters.values())


def disambiguate_phases(
    phases: dict[Path, RefinementResult]
) -> dict[Path, RefinementResult]:
    if not phases:
        return {}
    elif len(phases) == 1:
        return phases

    phases_group = group_phases(phases)

    result = {}

    for group in phases_group:
        all_fom = np.array([fom(phase, phases[phase]) for phase in group])
        all_phases = list(group.keys())

        best_phases = [all_phases[i] for i in np.where(all_fom == np.max(all_fom))[0]]

        for best_phase in best_phases:
            result[best_phase] = group[best_phase]

    return result


def _search_with_phase(
    phases: list[Path],
    peak_matcher: PeakMatcher,
    pattern_path: Path,
    all_phase_results: dict[Path, RefinementResult],
    max_phases: int = 5,
    top_n: int = 5,
    rpb_threshold: float = 1,
) -> dict[tuple[Path, ...], RefinementResult]:
    peak_obs = peak_matcher.peak_obs
    missing_obs = peak_matcher.missing
    peak_matchers = {}

    phases_set = set(phases)
    for phase, phase_result in all_phase_results.items():
        # skip the phase that has been used
        if phase in phases_set:
            continue
        peak_calc = phase_result.peak_data[["2theta", "intensity"]].values
        pm = PeakMatcher(peak_calc, missing_obs)
        peak_matchers[phase] = pm

    best_phases = get_best_phase(peak_matchers, top_n=top_n)

    refinement_results = batch_refine(
        pattern_path, [phases + [best_phase] for best_phase in best_phases]
    )
    subtree_to_be_expanded = {}

    for best_phase, result in zip(best_phases, refinement_results):
        necessary_phases = remove_unnecessary_phases(result, phases + [best_phase], rpb_threshold=rpb_threshold)
        if len(necessary_phases) != len(result.lst_data.phases_results):
            continue

        # not yet reach the maximum number of phases
        if len(phases) < max_phases - 1:
            subtree_to_be_expanded[best_phase] = result

    if subtree_to_be_expanded:
        subtree_to_be_expanded = disambiguate_phases(subtree_to_be_expanded)

    results = {}
    for best_phase, result in subtree_to_be_expanded.items():
        new_peak_matcher = PeakMatcher(
            result.peak_data[["2theta", "intensity"]].values, peak_obs
        )
        possible_phases = _search_with_phase(
            phases + [best_phase],
            new_peak_matcher,
            pattern_path,
            all_phase_results,
            max_phases=max_phases,
            top_n=top_n,
            rpb_threshold=rpb_threshold,
        )
        if possible_phases:
            results.update(possible_phases)
        else:
            results[tuple(list(phases) + [best_phase])] = result

    return results


def remove_unnecessary_phases(
    result: RefinementResult, cif_paths: list[Path], rpb_threshold: float = 1
) -> list[Path]:
    """
    Remove unnecessary phases from the result.

    If a phase cannot cause increase in RWP, it will be removed.
    """
    phases_results = {k: np.array(v) for k, v in result.plot_data.structs.items()}
    y_obs = np.array(result.plot_data.y_obs)
    y_calc = np.array(result.plot_data.y_calc)
    y_bkg = np.array(result.plot_data.y_bkg)

    cif_paths_dict = {cif_path.stem: cif_path for cif_path in cif_paths}

    original_rpb = rpb(y_calc, y_obs, y_bkg)

    new_phases = []

    for excluded_phase in phases_results:
        y_calc_excl = y_calc.copy()
        y_calc_excl -= phases_results[excluded_phase]

        new_rpb = rpb(y_calc_excl, y_obs, y_bkg)

        if new_rpb > original_rpb + rpb_threshold:
            new_phases.append(cif_paths_dict[excluded_phase])

    return new_phases


def remove_duplicate_results(
    results: dict[tuple[Path, ...], RefinementResult]
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
    max_phases: int = 5,
    top_n: int = 8,
    rpb_threshold: float = 1,
) -> dict:
    """Search for the best phase for a given pattern.

    Args:
        pattern_path : Path to the pattern file.
        cif_paths : List[Path]
            List of paths to the cif files.

    Returns
    -------
        Dict
            A dictionary containing the search result.
    """
    timer = time.time()
    logger.info(f"Searching for {pattern_path.stem}...")
    logger.info(f"Start peak detection...")
    eflech_worker = EflechWorker()
    peak_list = eflech_worker.run_peak_detection(
        pattern_path, wmin=10, wmax=60
    )
    logger.info(f"Peak detection finished. In total {len(peak_list)} peaks found.")
    peak_obs = peak_list[["2theta", "intensity"]].values

    all_phase_results = dict(
        zip(
            cif_paths,
            batch_refine(pattern_path, [[cif_path] for cif_path in cif_paths]),
        )
    )
    peak_matchers = {
        cif_path: PeakMatcher(
            all_phase_results[cif_path].peak_data[["2theta", "intensity"]].values,
            peak_obs,
        )
        for cif_path in cif_paths
    }

    best_phases = get_best_phase(peak_matchers, top_n=top_n)

    best_phases = list(
        disambiguate_phases({phase: all_phase_results[phase] for phase in best_phases})
    )

    results = {}
    for best_phase in best_phases:
        result = _search_with_phase(
            [best_phase],
            peak_matchers[best_phase],
            pattern_path=pattern_path,
            all_phase_results=all_phase_results,
            max_phases=max_phases,
            top_n=top_n,
            rpb_threshold=rpb_threshold,
        )
        if result:
            results.update(result)
        else:
            results[tuple([best_phase])] = all_phase_results[best_phase]

    all_rhos = [result.lst_data.rho for result in results.values()]

    # get the first natural break
    interval = jenkspy.jenks_breaks(all_rhos, n_classes=2)
    rho_cutoff = interval[1]
    results = {k: v for k, v in results.items() if v.lst_data.rho <= rho_cutoff}

    # remove duplicate combinations
    results = remove_duplicate_results(results)

    logger.info(f"Search time: {time.time() - timer:.2f} s, {len(results)} results found")

    return results
