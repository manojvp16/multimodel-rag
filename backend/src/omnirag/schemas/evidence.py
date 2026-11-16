
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


Modality = Literal[
    "text",
    "image",
    "table",
    "audio",
    "video",
]


class EvidenceUnit(BaseModel):
    """
    Represents one piece of evidence extracted from a document.

    A document can produce multiple EvidenceUnits:
    - Text extracted from a PDF page
    - An image embedded in a PDF
    - A table extracted from a PDF
    - Audio transcription
    - A video frame or scene description

    All evidence units belonging to the same document
    share the same document_id.
    """

    id: str = Field(
        default_factory=lambda: str(uuid4())
    )

    document_id: str
    source: str

    modality: Modality

    # Extracted text, transcription, table content,
    # or an image/video description.
    content: str = ""

    # Location information
    page_number: int | None = Field(default=None, ge=1)
    slide_number: int | None = Field(default=None, ge=1)
    sheet_name: str | None = None

    # Audio/video timestamp information (seconds)
    timestamp_start: float | None = Field(default=None, ge=0)
    timestamp_end: float | None = Field(default=None, ge=0)

    # Path to extracted media stored separately
    file_path: str | None = None

    # Additional extraction information
    metadata: dict[str, Any] = Field(
        default_factory=dict
    )
