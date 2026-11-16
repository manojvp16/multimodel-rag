import pymupdf
from omnirag.ingestion.pdf_processor import extract_pdf_text


def test_sample_text(tmp_path):
    path = tmp_path / 'sample.pdf'
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((50, 50), 'An independently generated sample document')
        pdf.save(path)
    evidence = extract_pdf_text(path)
    assert evidence
    assert all(item.modality == 'text' and item.content.strip() for item in evidence)
