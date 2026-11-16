from pydantic import Field

from omnirag.schemas.evidence import EvidenceUnit


class RetrievalChunk(EvidenceUnit):
    """A bounded piece of evidence, retaining all source location fields."""

    evidence_id: str
    chunk_index: int = Field(ge=0)
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)
