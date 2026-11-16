"""Readable source excerpts without changing indexed chunks or their offsets."""


def readable_excerpt(chunk: dict, evidence: dict | None) -> str:
    content = chunk["content"]
    if not evidence or chunk.get("modality") not in {"text", "table"}:
        return content
    original = evidence.get("content", "")
    start, end = chunk.get("char_start"), chunk.get("char_end")
    if not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end <= len(original):
        return content
    if original[start:end] != content:
        return content
    # Repair legacy mid-word boundaries using actual source characters only.
    # Cap extension for pathological long tokens such as encoded data.
    lower, upper = max(0, start - 100), min(len(original), end + 100)
    while start > lower and not original[start - 1].isspace() and not original[start].isspace():
        start -= 1
    while end < upper and not original[end - 1].isspace() and not original[end].isspace():
        end += 1
    return original[start:end].strip()
