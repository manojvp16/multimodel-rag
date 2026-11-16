
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DocumentRecord(BaseModel):
    """Metadata for an uploaded document."""

    document_id: str

    filename: str

    status: Literal[
        "uploaded",
        "processing",
        "completed",
        "failed",
    ] = "completed"

    created_at: datetime

    page_count: int = Field(ge=0)

    evidence_count: int = Field(ge=0)

    file_size_bytes: int = Field(ge=0)

    storage_path: str

    modality_counts: dict[str, int] = Field(
        default_factory=dict
    )
