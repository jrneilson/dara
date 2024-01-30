from __future__ import annotations

from itertools import zip_longest
from pathlib import Path
from subprocess import TimeoutExpired
from typing import Literal

import numpy as np
import ray
from pymatgen.core import Structure
from sklearn.cluster import AgglomerativeClustering
from treelib import Node, Tree

from dara import do_refinement_no_saving
from dara.eflech_worker import EflechWorker
from dara.result import RefinementResult
from dara.search.node import SearchNodeData
from dara.search.peak_matcher import PeakMatcher
from dara.utils import rpb, get_number


@ray.remote(num_cpus=1)
def remote_do_refinement_no_saving(
    pattern_path: Path,
    cif_paths: list[Path],
    instrument_name: str,
    phase_params: dict[str, ...] | None,
    refinement_params: dict[str, float] | None,
) -> RefinementResult | None:
    if len(cif_paths) == 0:
        return None
    try:
        result = do_refinement_no_saving(
            pattern_path,
            cif_paths,
            instrument_name=instrument_name,
            phase_params=phase_params,
            refinement_params=refinement_params,
        )
    except (RuntimeError, TimeoutExpired):
        return None
    if result.lst_data.rpb == 100:
        return None
    return result


@ray.remote(num_cpus=1)
def remote_peak_matching(
    peak_calc: np.ndarray,
    missing_peaks: np.ndarray,
    return_type: Literal["PeakMatcher", "score", "jaccard"],
) -> PeakMatcher | float:
    pm = PeakMatcher(peak_calc, missing_peaks)
    if return_type == "PeakMatcher":
        return pm
    elif return_type == "score":
        return pm.score()
    elif return_type == "jaccard":
        return pm.jaccard_index()
    else:
        raise ValueError(f"return_type {return_type} is not supported.")


def batch_peak_matching(
    peak_calcs: list[np.ndarray],
    peak_obs: np.ndarray | list[np.ndarray],
    return_type: Literal["PeakMatcher", "score", "jaccard"] = "PeakMatcher",
) -> list[PeakMatcher | float]:
    if isinstance(peak_obs, np.ndarray):
        peak_obs = [peak_obs] * len(peak_calcs)
    handles = [
        remote_peak_matching.remote(peak_calc, peak_obs_, return_type=return_type)
        for peak_calc, peak_obs_ in zip_longest(peak_calcs, peak_obs, fillvalue=None)
    ]
    return ray.get(handles)


def batch_refinement(
    pattern_path: Path,
    cif_paths: list[list[Path]],
    instrument_name: str = "Aeris-fds-Pixcel1d-Medipix3",
    phase_params: dict[str, ...] | None = None,
    refinement_params: dict[str, float] | None = None,
) -> list[RefinementResult]:
    handles = [
        remote_do_refinement_no_saving.remote(
            pattern_path,
            cif_paths,
            instrument_name=instrument_name,
            phase_params=phase_params,
            refinement_params=refinement_params,
        )
        for cif_paths in cif_paths
    ]
    return ray.get(handles)


def calculate_fom(phase_path: Path, result: RefinementResult) -> float:
    a = b = c = d = 1.0
    b1_threshold = 2e-2
    k2_threshold = 1e-5

    initial_lattice_abc = Structure.from_file(phase_path.as_posix()).lattice.abc

    refined_a = result.lst_data.phases_results[phase_path.stem].a
    refined_b = result.lst_data.phases_results[phase_path.stem].b
    refined_c = result.lst_data.phases_results[phase_path.stem].c

    geweicht = result.lst_data.phases_results[phase_path.stem].gewicht
    geweicht = get_number(geweicht)

    b1 = get_number(result.lst_data.phases_results[phase_path.stem].B1) or 0
    k2 = get_number(result.lst_data.phases_results[phase_path.stem].k2) or 0

    if refined_a is None or geweicht is None:
        return 0

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
    all_phases_result: dict[Path, RefinementResult], distance_threshold: float = 0.1
) -> dict[Path, dict[str, float | int]]:
    if len(all_phases_result) <= 1:
        return {
            phase: {"group_id": 0, "fom": calculate_fom(phase, result)}
            for phase, result in all_phases_result.items()
        }

    peaks = []

    for phase, result in all_phases_result.items():
        all_peaks = result.peak_data
        peaks.append(
            all_peaks[all_peaks["phase"] == phase.stem][["2theta", "intensity"]].values
        )

    # get distance matrix
    distance_matrix = np.zeros((len(all_phases_result), len(all_phases_result)))

    for i in range(len(all_phases_result)):
        for j in range(len(all_phases_result)):
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

    grouped_result = {}
    for i, cluster in enumerate(clusterer.labels_):
        phase = list(all_phases_result.keys())[i]
        result = list(all_phases_result.values())[i]
        grouped_result[phase] = {
            "group_id": cluster,
            "fom": calculate_fom(phase, result),
        }

    return grouped_result


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


class SearchTree(Tree):
    def __init__(
        self,
        max_phases: float,
        pattern_path: Path,
        cif_paths: list[Path],
        pinned_phases: list[Path] | None = None,
        top_n: int = 8,
        rpb_threshold: float = 1,
        refine_params: dict[str, ...] | None = None,
        phase_params: dict[str, ...] | None = None,
        instrument_name: str = "Aeris-fds-Pixcel1d-Medipix3",
        maximum_grouping_distance: float = 0.1,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.max_phases = max_phases
        self.pattern_path = pattern_path
        self.cif_paths = cif_paths
        self.pinned_phases = pinned_phases if pinned_phases is not None else []
        self.top_n = top_n
        self.rpb_threshold = rpb_threshold
        self.refinement_params = refine_params if refine_params is not None else {}
        self.phase_params = phase_params if phase_params is not None else {}
        self.instrument_name = instrument_name
        self.maximum_grouping_distance = maximum_grouping_distance

        self._peak_obs = self._detect_peak_in_pattern()
        self._create_root_node()

    def _detect_peak_in_pattern(self) -> np.ndarray:
        eflech_worker = EflechWorker()
        peak_list = eflech_worker.run_peak_detection(
            self.pattern_path,
            wmin=self.refinement_params.get("wmin", None),
            wmax=self.refinement_params.get("wmax", None),
        )
        peak_obs = peak_list[["2theta", "intensity"]].values
        return peak_obs

    def _create_root_node(self) -> Node:
        pinned_phases_set = set(self.pinned_phases)
        cif_paths = [
            cif_path for cif_path in self.cif_paths if cif_path not in pinned_phases_set
        ]
        all_phases_result = self.get_all_phases_result(
            cif_paths, pinned_phases=self.pinned_phases
        )

        # clean up cif paths (if no result, remove from list)
        all_phases_result = {
            phase: result
            for phase, result in all_phases_result.items()
            if result is not None
        }

        root_node = Node(
            data=SearchNodeData(
                all_phases_result=all_phases_result,
                current_result=self._batch_refine([self.pinned_phases])[0],
                current_phases=self.pinned_phases,
            ),
        )
        self.add_node(root_node)
        return root_node

    def expand_node(self, nid: str) -> list[str]:
        node = self.get_node(nid)
        if node is None:
            raise ValueError(f"Node with id {nid} does not exist.")
        if node.data.status != "pending":
            raise ValueError(f"Node with id {nid} is not expandable.")

        node.data.status = "running"
        try:
            all_phases_result = node.data.all_phases_result
            current_phases_set = set(node.data.current_phases)

            # remove phases that are already in the current result
            all_phases_result = {
                phase: result
                for phase, result in all_phases_result.items()
                if phase not in current_phases_set
            }
            best_phases, scores = self.get_best_phases(
                all_phases_result, node.data.current_result
            )

            node.data.peak_matcher_scores = scores

            new_results = self.get_all_phases_result(
                best_phases, pinned_phases=node.data.current_phases
            )

            # group the results
            grouped_results = group_phases(
                new_results,
                distance_threshold=self.maximum_grouping_distance,
            )

            for phase, new_result in new_results.items():
                new_phases = node.data.current_phases + [phase]

                group_id = grouped_results[phase]["group_id"]
                fom = grouped_results[phase]["fom"]
                is_best_result_in_group = fom == max(
                    [
                        grouped_results[phase_]["fom"]
                        for phase_ in grouped_results
                        if grouped_results[phase_]["group_id"] == group_id
                    ]
                )

                weight_fractions = new_result.get_phase_weights(normalize=True)

                if new_result is None:
                    status = "error"
                elif any(wt < 0.01 for wt in weight_fractions.values()):
                    status = "low_weight_fraction"
                elif node.data.current_result is not None and (
                    (
                        len(
                            remove_unnecessary_phases(
                                new_result, new_phases, rpb_threshold=self.rpb_threshold
                            )
                        )
                        != len(new_phases)
                    )
                    or (
                        new_result.lst_data.rpb
                        >= node.data.current_result.lst_data.rpb + self.rpb_threshold
                    )
                ):
                    status = "no_improvement"
                elif not is_best_result_in_group:
                    status = "similar_structure"
                elif len(new_phases) >= self.max_phases:
                    status = "max_depth"
                else:
                    status = "pending"

                new_node = Node(
                    data=SearchNodeData(
                        all_phases_result=all_phases_result,
                        current_result=new_result,
                        current_phases=new_phases,
                        status=status,
                        group_id=group_id,
                        fom=fom,
                    ),
                )
                self.add_node(new_node, parent=nid)
        except Exception:
            node.data.status = "error"
            raise

        node.data.status = "expanded"

        return [
            child.identifier
            for child in self.children(nid)
            if self.get_node(child.identifier).data.status == "pending"
        ]

    def get_search_results(self) -> dict[tuple[Path, ...], RefinementResult]:
        results = {}
        for node in self.nodes.values():
            if node.data.status in {"expanded", "max_depth"} and all(
                child.data.status not in {"expanded", "max_depth"}
                for child in self.children(node.identifier)
            ):
                results[tuple(node.data.current_phases)] = node.data.current_result
        return results

    def get_best_phases(
        self,
        all_phases_result: dict[Path, RefinementResult],
        current_result: RefinementResult | None = None,
    ) -> tuple[list[Path], dict[Path, float]]:
        if current_result is None:
            missing_peaks = self._peak_obs
        else:
            current_peak_calc = current_result.peak_data[["2theta", "intensity"]].values
            missing_peaks = PeakMatcher(current_peak_calc, self._peak_obs).missing

        if len(missing_peaks) == 0:
            return [], {}

        peak_calcs = [
            refinement_result.peak_data[
                refinement_result.peak_data["phase"] == phase.stem
            ][["2theta", "intensity"]].values
            for phase, refinement_result in all_phases_result.items()
        ]
        scores = dict(
            zip_longest(
                all_phases_result.keys(),
                batch_peak_matching(peak_calcs, missing_peaks, return_type="score"),
                fillvalue=None,
            )
        )

        return (
            sorted(scores, key=lambda x: scores[x], reverse=True)[: self.top_n],
            scores,
        )

    def get_all_phases_result(
        self, phases: list[Path], pinned_phases: list[Path] | None = None
    ) -> dict[Path, RefinementResult | None]:
        if pinned_phases is None:
            pinned_phases = []

        all_phases_result = dict(
            zip_longest(
                phases,
                self._batch_refine([[phase] + pinned_phases for phase in phases]),
                fillvalue=None,
            )
        )
        return all_phases_result

    def _batch_refine(
        self,
        all_references: list[list[Path]],
    ) -> list[RefinementResult]:
        return batch_refinement(
            self.pattern_path,
            all_references,
            instrument_name=self.instrument_name,
            phase_params=self.phase_params,
            refinement_params=self.refinement_params,
        )
