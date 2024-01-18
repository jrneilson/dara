from __future__ import annotations

from pathlib import Path

import jenkspy
from tqdm import tqdm

from dara import do_refinement_no_saving
from dara.eflech_worker import EflechWorker
from dara.result import RefinementResult
from dara.search.peak_matcher import PeakMatcher


def get_best_phase(peak_matchers: dict[Path, PeakMatcher], top_n: int = 10) -> list[Path]:
    return sorted(peak_matchers, key=lambda x: peak_matchers[x].score(), reverse=True)[:top_n]


def _search_with_phase(
    phases: list[Path],
    peak_matcher: PeakMatcher,
    pattern_path: Path,
    all_phase_results: dict[Path, RefinementResult],
    max_phases: int = 4,
    top_n: int = 5,
    last_rwp: float = 100,
    rwp_threshold: float = 0.1,
) -> dict:
    result = do_refinement_no_saving(
        pattern_path,
        phases,
        refinement_params={"wmin": 10, "wmax": 60},
        phase_params={
            "gewicht": "0_0",
            "k1": "0_0^0.01",
            "k2": "0_0^0.01",
            "b1": "0_0^0.01",
            "rp": 4,
        },
    )
    output = f"Rwp = {result.lst_data.rwp}%: "
    for p in phases:
        output += f"{p.name} "
    print(output)

    # early stopping
    if result.lst_data.rwp >= last_rwp - rwp_threshold:
        return {}

    # reach max phases
    if len(phases) >= max_phases:
        return {tuple(phases): result}

    missing_obs = peak_matcher.missing
    peak_matchers = {}

    for phase, phase_result in all_phase_results.items():
        peak_calc = phase_result.peak_data[["2theta", "intensity"]].values
        pm = PeakMatcher(peak_calc, missing_obs)
        peak_matchers[phase] = pm

    best_phases = get_best_phase(peak_matchers, top_n=top_n)

    results = {}
    for best_phase in best_phases:
        possible_phases = _search_with_phase(
            phases + [best_phase],
            peak_matchers[best_phase],
            pattern_path,
            all_phase_results,
            max_phases=max_phases,
            top_n=top_n,
            last_rwp=result.lst_data.rwp,
        )
        results.update(possible_phases)

    # if no better result is found, return the current result
    if not results:
        return {tuple(phases): result}

    return results


def search_phases(
    pattern_path: Path,
    cif_paths: list[Path],
    max_phases: int = 4,
    top_n: int = 5,
    rwp_improvement_threshold: float = 0.5,
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
    eflech_worker = EflechWorker()
    peak_list = eflech_worker.run_peak_detection(pattern_path, wmin=10, wmax=60)
    peak_obs = peak_list[["2theta", "intensity"]].values

    all_phase_results = {}
    peak_matchers = {}
    for cif_path in tqdm(cif_paths, desc="Refining single phases"):
        result = do_refinement_no_saving(
            pattern_path,
            [cif_path],
            refinement_params={"wmin": 10, "wmax": 60},
            phase_params={
                "gewicht": "0_0",
                "k1": "0_0^0.01",
                "k2": "0_0^0.01",
                "b1": "0_0^0.01",
                "rp": 4,
            },
        )
        all_phase_results[cif_path] = result
        peak_calc = result.peak_data[["2theta", "intensity"]].values
        pm = PeakMatcher(peak_calc, peak_obs)
        peak_matchers[cif_path] = pm

    best_phases = get_best_phase(peak_matchers, top_n=top_n)

    results = {}
    for best_phase in best_phases:
        result = _search_with_phase(
            [best_phase],
            peak_matchers[best_phase],
            pattern_path=pattern_path,
            all_phase_results=all_phase_results,
            max_phases=max_phases,
            top_n=top_n,
            rwp_threshold=rwp_improvement_threshold,
        )
        results.update(result)

    all_rwps = [result.lst_data.rwp for result in results.values()]

    # get the first natural break
    interval = jenkspy.jenks_breaks(all_rwps, n_classes=2)
    rwp_cutoff = interval[1]

    results = {k: v for k, v in results.items() if v.lst_data.rwp <= rwp_cutoff}

    return results
