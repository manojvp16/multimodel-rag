
import pymupdf
import pytest

from PIL import Image

from omnirag.ingestion.pdf_processor import (
    extract_pdf_text,
    extract_pdf_evidence,
)


@pytest.fixture
def sample_multimodal_pdf(tmp_path):
    """Create a PDF containing text, an image, and a table."""

    pdf_path = tmp_path / "sample_multimodal.pdf"

    # Create a test image.
    image_path = tmp_path / "sample.png"

    image = Image.new(
        "RGB",
        (200, 100),
        color="blue"
    )

    image.save(image_path)

    # Create PDF.
    doc = pymupdf.open()

    page = doc.new_page(
        width=600,
        height=800
    )

    # Add text.
    page.insert_text(
        (50, 50),
        "OmniRAG Multimodal PDF Test"
    )

    page.insert_text(
        (50, 80),
        "This document contains sample text."
    )

    # Add embedded image.
    page.insert_image(
        pymupdf.Rect(50, 120, 250, 220),
        filename=str(image_path)
    )

    # Draw a simple 2x2 table.
    x0, y0 = 50, 300
    x1, y1 = 350, 400

    # Horizontal lines.
    page.draw_line(
        (x0, y0),
        (x1, y0)
    )

    page.draw_line(
        (x0, 350),
        (x1, 350)
    )

    page.draw_line(
        (x0, y1),
        (x1, y1)
    )

    # Vertical lines.
    page.draw_line(
        (x0, y0),
        (x0, y1)
    )

    page.draw_line(
        (200, y0),
        (200, y1)
    )

    page.draw_line(
        (x1, y0),
        (x1, y1)
    )

    # Table cell contents.
    page.insert_text((70, 330), "Product")
    page.insert_text((220, 330), "Price")
    page.insert_text((70, 380), "Laptop")
    page.insert_text((220, 380), "50000")

    doc.save(pdf_path)
    doc.close()

    return pdf_path


def test_extract_pdf_text(sample_multimodal_pdf):

    evidence = extract_pdf_text(
        sample_multimodal_pdf
    )

    assert len(evidence) >= 1
    assert evidence[0].modality == "text"
    assert "OmniRAG" in evidence[0].content


def test_extract_all_modalities(
    sample_multimodal_pdf,
    tmp_path
):

    image_dir = tmp_path / "extracted_images"

    evidence = extract_pdf_evidence(
        sample_multimodal_pdf,
        output_dir=image_dir,
        document_id="test-document-001"
    )

    modalities = {
        item.modality
        for item in evidence
    }

    assert "text" in modalities
    assert "image" in modalities
    assert "table" in modalities


def test_all_evidence_has_same_document_id(
    sample_multimodal_pdf,
    tmp_path
):

    evidence = extract_pdf_evidence(
        sample_multimodal_pdf,
        output_dir=tmp_path / "images",
        document_id="shared-document-id"
    )

    assert len(evidence) > 0

    assert all(
        item.document_id == "shared-document-id"
        for item in evidence
    )


def test_extracted_images_exist(
    sample_multimodal_pdf,
    tmp_path
):

    image_dir = tmp_path / "images"

    evidence = extract_pdf_evidence(
        sample_multimodal_pdf,
        output_dir=image_dir
    )

    image_evidence = [
        item for item in evidence
        if item.modality == "image"
    ]

    assert len(image_evidence) >= 1

    for item in image_evidence:
        assert item.file_path is not None
        assert item.file_path.endswith(
            (".png", ".jpg", ".jpeg")
        )

        from pathlib import Path

        assert Path(item.file_path).exists()


def test_table_metadata(
    sample_multimodal_pdf,
    tmp_path
):

    evidence = extract_pdf_evidence(
        sample_multimodal_pdf,
        output_dir=tmp_path / "images"
    )

    tables = [
        item for item in evidence
        if item.modality == "table"
    ]

    assert len(tables) >= 1

    table = tables[0]

    assert table.page_number == 1
    assert table.metadata["row_count"] >= 2
    assert table.metadata["column_count"] >= 2


def test_missing_pdf():

    with pytest.raises(FileNotFoundError):
        extract_pdf_evidence(
            "missing_file.pdf"
        )


def test_invalid_file_extension(tmp_path):

    text_file = tmp_path / "sample.txt"
    text_file.write_text("This is not a PDF.")

    with pytest.raises(ValueError):
        extract_pdf_evidence(text_file)
