from uuid import UUID
from pydantic import BaseModel, Field, field_validator


class SearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    document_ids: list[UUID] = Field(default_factory=list, max_length=100)
    top_k: int = Field(default=5, ge=1, le=20)
    score_threshold: float = Field(default=0.25, ge=-1, le=1)

    @field_validator("question")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Question cannot be blank.")
        return value.strip()
