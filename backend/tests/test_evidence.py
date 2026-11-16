
import pytest

from omnirag.schemas.evidence import EvidenceUnit


def test_create_text_evidence():
    evidence = EvidenceUnit(
        document_id="doc-001",
        source="sample.pdf",
        modality="text",
        page_number=1,
        content="This is sample PDF text."
    )

    assert evidence.document_id == "doc-001"
    assert evidence.source == "sample.pdf"
    assert evidence.modality == "text"
    assert evidence.page_number == 1


def test_create_image_evidence():
    evidence = EvidenceUnit(
        document_id="doc-001",
        source="sample.pdf",
        modality="image",
        page_number=2,
        file_path="storage/images/image_001.png",
        metadata={"width": 800, "height": 600}
    )

    assert evidence.modality == "image"
    assert evidence.file_path is not None
    assert evidence.metadata["width"] == 800


def test_create_audio_evidence():
    evidence = EvidenceUnit(
        document_id="doc-002",
        source="meeting.mp3",
        modality="audio",
        timestamp_start=10.5,
        timestamp_end=20.0,
        content="We discussed the project."
    )

    assert evidence.timestamp_start == 10.5
    assert evidence.timestamp_end == 20.0


def test_evidence_ids_are_unique():
    evidence1 = EvidenceUnit(
        document_id="doc-001",
        source="sample.pdf",
        modality="text"
    )

    evidence2 = EvidenceUnit(
        document_id="doc-001",
        source="sample.pdf",
        modality="text"
    )

    assert evidence1.id != evidence2.id


def test_invalid_page_number():
    with pytest.raises(ValueError):
        EvidenceUnit(
            document_id="doc-001",
            source="sample.pdf",
            modality="text",
            page_number=0
        )


def test_invalid_modality():
    with pytest.raises(ValueError):
        EvidenceUnit(
            document_id="doc-001",
            source="sample.pdf",
            modality="document"
        )


def test_metadata_is_independent():
    evidence1 = EvidenceUnit(
        document_id="doc-001",
        source="sample.pdf",
        modality="text"
    )

    evidence2 = EvidenceUnit(
        document_id="doc-001",
        source="sample.pdf",
        modality="text"
    )

    evidence1.metadata["method"] = "pymupdf"

    assert "method" not in evidence2.metadata
