import pytest

from omnirag.ingestion.chunker import chunk_evidence
from omnirag.schemas.evidence import EvidenceUnit


def test_chunks_cover_source_preserve_provenance_and_repeat_stably():
    item = EvidenceUnit(document_id="doc", source="report.pdf", modality="text",
                        page_number=3, content=("A paragraph about retrieval.\n\n" * 100))
    chunks = chunk_evidence([item], chunk_size=100, chunk_overlap=20)
    assert len(chunks) > 1
    covered = set()
    for index, chunk in enumerate(chunks):
        assert chunk.content == item.content[chunk.char_start:chunk.char_end]
        assert 0 < len(chunk.content) <= 100
        assert chunk.evidence_id == item.id
        assert chunk.page_number == 3
        assert chunk.source == "report.pdf"
        assert chunk.chunk_index == index
        covered.update(range(chunk.char_start, chunk.char_end))
    assert covered == set(range(len(item.content)))
    assert chunks == chunk_evidence([item], chunk_size=100, chunk_overlap=20)
    assert len({chunk.id for chunk in chunks}) == len(chunks)


def test_small_table_intact_and_empty_media_skipped():
    table = EvidenceUnit(document_id="doc", source="a.pdf", modality="table",
                         content="Product\tPrice\nLaptop\t50000")
    image = EvidenceUnit(document_id="doc", source="a.pdf", modality="image", file_path="image.png")
    empty = EvidenceUnit(document_id="doc", source="a.pdf", modality="text", content="  ")
    chunks = chunk_evidence([table, image, empty])
    assert len(chunks) == 1
    assert chunks[0].content == table.content
    assert chunks[0].modality == "table"


@pytest.mark.parametrize("size,overlap", [(0, 0), (10, -1), (10, 10)])
def test_invalid_configuration(size, overlap):
    with pytest.raises(ValueError):
        chunk_evidence([], size, overlap)


def test_unbroken_text_and_maximum_overlap_terminate():
    item = EvidenceUnit(document_id="doc", source="a", modality="text", content="x" * 25)
    chunks = chunk_evidence([item], 10, 9)
    assert chunks[-1].char_end == 25
    assert all(len(chunk.content) == 10 for chunk in chunks)


def test_overlap_does_not_start_inside_normal_words():
    text = 'Developed backend applications using Java Spring Boot and PostgreSQL. ' * 20
    item = EvidenceUnit(document_id='doc', source='resume.pdf', modality='text', content=text)
    chunks = chunk_evidence([item], chunk_size=100, chunk_overlap=23)
    covered = set()
    for chunk in chunks:
        start = chunk.char_start
        assert start == 0 or text[start].isspace() or text[start - 1].isspace()
        assert chunk.content == text[start:chunk.char_end]
        assert len(chunk.content) <= 100
        covered.update(range(start, chunk.char_end))
    assert covered == set(range(len(text)))
