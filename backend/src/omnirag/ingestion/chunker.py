"""Prepare textual evidence for retrieval without making model calls."""

from uuid import NAMESPACE_URL, uuid5

from omnirag.schemas.chunk import RetrievalChunk
from omnirag.schemas.evidence import EvidenceUnit


def chunk_evidence(
    evidence: list[EvidenceUnit],
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
) -> list[RetrievalChunk]:
    """Split text into character-bounded windows, preferring natural boundaries.

    Offsets refer to the original evidence content. Small tables stay intact;
    large tables prefer row boundaries but may split an oversized row. Raw
    images/audio/video are retained as evidence, not embedded as empty text.
    """
    if chunk_size <= 0 or not 0 <= chunk_overlap < chunk_size:
        raise ValueError("Require chunk_size > 0 and 0 <= chunk_overlap < chunk_size.")

    chunks = []
    for item in evidence:
        if item.modality not in {"text", "table"} or not item.content.strip():
            continue

        start = 0
        index = 0
        while start < len(item.content):
            end = min(start + chunk_size, len(item.content))
            if end < len(item.content):
                # A boundary in the latter half avoids tiny chunks and ensures
                # forward progress even when overlap is close to chunk_size.
                lower = start + max(chunk_size // 2, chunk_overlap + 1)
                separators = ("\n",) if item.modality == "table" else ("\n\n", "\n", " ")
                for separator in separators:
                    boundary = item.content.rfind(separator, lower, end)
                    if boundary >= lower:
                        end = boundary + len(separator)
                        break

            content = item.content[start:end]
            if content.strip():
                identity = f"omnirag:{item.document_id}:{item.id}:{start}:{end}:{content}"
                chunks.append(RetrievalChunk(
                    **item.model_dump(exclude={"id", "content"}),
                    id=str(uuid5(NAMESPACE_URL, identity)),
                    content=content,
                    evidence_id=item.id,
                    chunk_index=index,
                    char_start=start,
                    char_end=end,
                ))
                index += 1
            if end == len(item.content):
                break
            next_start = end - chunk_overlap
            # An overlap offset may land inside "Developed", yielding "veloped".
            # Move to the next word; the previous chunk already covers the gap.
            if next_start > 0 and not item.content[next_start - 1].isspace():
                boundary = next_start
                while boundary < end and not item.content[boundary].isspace():
                    boundary += 1
                if boundary < end:
                    next_start = boundary
            start = next_start

    return chunks
