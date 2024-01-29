"""Pydantic document schemas for jobflow jobs."""

from typing import Optional

from pydantic import BaseModel, Field

from dara.cif import Cif
from dara.prediction.core import PhasePredictor
from dara.result import RefinementResult
from dara.utils import datetime_str
from dara.xrd import XRDData


class RefinementDocument(BaseModel):
    """Refinement document schema."""

    task_label: Optional[str] = Field("refine", description="The name of the task.")
    last_updated: str = Field(
        default_factory=datetime_str,
        description="Timestamp of when the document was last updated.",
    )
    result: RefinementResult = Field(description="The result of the refinement.")
    xrd_data: XRDData = Field(description="The input XRD data.")
    input_cifs: list[Cif] = Field(description="The input CIFs.")
    refinement_params: Optional[dict] = Field(
        None, description="The refinement parameters."
    )
    phase_params: Optional[dict] = Field(None, description="The phase parameters.")
    instrument_name: Optional[str] = Field(None, description="The instrument name.")


class PhaseSearchDocument(BaseModel):
    """Phase search document schema."""

    task_label: Optional[str] = Field(
        "phase_search", description="The name of the task."
    )
    last_updated: str = Field(
        default_factory=datetime_str,
        description="Timestamp of when the document was last updated.",
    )
    results: Optional[list[RefinementResult]] = Field(
        None, description="The result of the refinement."
    )
    run_final_refinement: bool = True
    cifs_folder_name: str = "cifs"
    xrd_data: XRDData = Field(description="The input XRD data.")
    input_cifs: list[Cif] = Field(description="The input CIFs.")
    precursors: Optional[list[str]] = Field(None, description="The precursor formulas.")
    phase_predictor: Optional[PhasePredictor] = Field(
        None, description="The phase predictor."
    )
    predict_kwargs: Optional[dict] = Field(
        None, description="The kwargs for the phase predictor."
    )
    search_kwargs: Optional[dict] = Field(
        None, description="The kwargs for the search."
    )
    final_refinement_params: Optional[dict] = Field(
        None, description="The final refinement parameters."
    )
