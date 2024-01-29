"""Jobflow jobs for DARA."""
from __future__ import annotations

from dataclasses import dataclass

from jobflow import Maker, job

from dara.cif import Cif
from dara.refine import do_refinement, do_refinement_no_saving
from dara.schema import PhaseSearchDocument, RefinementDocument
from dara.xrd import XRDData


@dataclass
class RefinementMaker(Maker):
    """Maker to create a job for performing Rietveld refinement using BGMN.

    Args:
        name: The name of the job. This is automatically created if not provided.
    """

    name: str = "refine"
    save: bool = True

    @job(output_schema=RefinementDocument)
    def make(
        self,
        xrd_data: XRDData,
        cifs: list[Cif],
        instrument_name: str = "Aeris-fds-Pixcel1d-Medipix3",
        phase_params: dict | None = None,
        refinement_params: dict | None = None,
        show_progress: bool = True,
    ):
        """Perform Rietveld refinement.

        Args:
            xrd_data: _description_
            cifs: _description_

        Returns
        -------
            _description_
        """
        pattern_path = "xrd_data.xy"
        xrd_data.to_xy_file(pattern_path)

        phase_paths = []
        for cif in cifs:
            cif_path = f"{next(iter(cif.data.keys()))}.cif"
            phase_paths.append(cif_path)

            with open(cif_path, "w") as f:
                f.write(str(cif))

        args = {
            "pattern_path": pattern_path,
            "phase_paths": phase_paths,
            "instrument_name": instrument_name,
            "phase_params": phase_params,
            "refinement_params": refinement_params,
            "show_progress": show_progress,
        }

        result = do_refinement(**args) if self.save else do_refinement_no_saving(**args)

        doc = RefinementDocument(result=result)
        doc.task_label = self.name

        return doc


@dataclass
class PhaseSearchMaker(Maker):
    """Maker to create a job for performing phase search using BGMN."""

    name: str = "phase_search"
    path_to_icsd: str = (
        "$HOME/ICSD_2024/ICSD_2024_experimental_inorganic/experimental_inorganic"
    )

    @job(output_schema=PhaseSearchDocument)
    def make(
        self,
        xrd_data: XRDData,
        cifs: list[Cif],
        instrument_name: str = "Aeris-fds-Pixcel1d-Medipix3",
        phase_params: dict | None = None,
        refinement_params: dict | None = None,
        show_progress: bool = True,
    ):
        doc = PhaseSearchDocument()
        doc.task_label = self.name
        return doc
