"""Pydantic document schemas for jobflow jobs."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from dara.result import RefinementResult
from dara.utils import datetime_str


class RefinementDocument(BaseModel):
    """Refinement document schema."""

    task_label: Optional[str] = Field(None, description="The name of the task.")
    last_updated: datetime = Field(
        default_factory=datetime_str,
        description="Timestamp of when the document was last updated.",
    )
    result: Optional[RefinementResult] = Field(
        None, description="The result of the refinement."
    )


class PhaseSearchDocument(BaseModel):
    """Phase search document schema."""

    task_label: Optional[str] = Field(None, description="The name of the task.")
    last_updated: datetime = Field(
        default_factory=datetime_str,
        description="Timestamp of when the document was last updated.",
    )
    results: Optional[list[RefinementResult]] = Field(
        None, description="The result of the refinement."
    )
