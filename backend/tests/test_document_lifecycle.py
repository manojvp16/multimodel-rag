from io import BytesIO
from uuid import uuid4

import pymupdf
import pytest
from fastapi import FastAPI, HTTPException, UploadFile

from omnirag.api.routes import documents
from omnirag.storage import file_storage


@pytest.fixture
def storage(tmp_path, monkeypatch):
    monkeypatch.setattr(file_storage, "get_storage_root", lambda: tmp_path)
    monkeypatch.setattr(documents, "get_storage_root", lambda: tmp_path)
    return tmp_path


def test_upload_chunks_read_and_delete(storage):
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((50, 50), "OmniRAG retrieval preparation")
        data = pdf.tobytes()
    record = documents.upload_document(UploadFile(filename="report.pdf", file=BytesIO(data)))
    assert record.status == "completed"
    assert file_storage.get_document(record.document_id)["filename"] == "report.pdf"
    result = documents.get_document_chunks_route(record.document_id, skip=0, limit=50)
    assert result["total"] >= 1
    assert result["chunks"][0]["source"] == "report.pdf"
    assert (storage / "chunks" / f"{record.document_id}.json").exists()
    assert documents.get_document_chunks_route(record.document_id, skip=100, limit=1)["chunks"] == []
    documents.delete_document(record.document_id)
    assert not list(storage.rglob("*.json"))
    assert not list(storage.rglob("*.pdf"))
    with pytest.raises(HTTPException) as error:
        documents.delete_document(record.document_id)
    assert error.value.status_code == 404


def test_processing_value_error_removes_all_partial_artifacts(storage, monkeypatch):
    def fail(**kwargs):
        directory = kwargs["output_dir"]
        directory.mkdir(parents=True)
        (directory / "partial.png").write_bytes(b"partial")
        raise ValueError("extraction failed")
    monkeypatch.setattr(documents, "extract_pdf_evidence", fail)
    with pymupdf.open() as pdf:
        pdf.new_page()
        data = pdf.tobytes()
    with pytest.raises(HTTPException) as error:
        documents.upload_document(UploadFile(filename="report.pdf", file=BytesIO(data)))
    assert error.value.status_code == 400
    assert not list(storage.rglob("*.png"))
    assert not list(storage.rglob("*.pdf"))


def test_old_upload_chunks_and_invalid_id(storage):
    document_id = str(uuid4())
    file_storage._write_json(storage / "metadata" / f"{document_id}.json", {"document_id": document_id})
    file_storage._write_json(storage / "evidence" / f"{document_id}.json", [{
        "document_id": document_id, "id": "old-evidence", "source": "old.pdf",
        "modality": "text", "content": "Previously uploaded evidence", "page_number": 1,
    }])
    assert documents.get_document_chunks_route(document_id, 0, 50)["total"] == 1
    with pytest.raises(HTTPException) as error:
        documents.get_document_chunks_route("invalid", 0, 50)
    assert error.value.status_code == 400


def test_routes_register():
    app = FastAPI()
    app.include_router(documents.router)
    assert "/api/v1/documents/{document_id}/chunks" in app.openapi()["paths"]
