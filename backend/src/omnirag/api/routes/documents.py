
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pymupdf

from fastapi import (
    APIRouter,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)

from omnirag.schemas.document import DocumentRecord
from omnirag.schemas.evidence import EvidenceUnit
from omnirag.ingestion.chunker import chunk_evidence

from omnirag.ingestion.pdf_processor import (
    extract_pdf_evidence,
)

from omnirag.storage.file_storage import (
    get_storage_root,
    save_uploaded_pdf,
    save_document_data,
    get_document,
    list_documents,
    get_document_evidence,
    get_document_chunks,
    delete_document_data,
)


router = APIRouter(
    prefix="/api/v1/documents",
    tags=["Documents"],
)


@router.post(
    "/upload",
    response_model=DocumentRecord,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(
    file: UploadFile = File(...),
):
    """
    Upload a PDF and extract text, images, tables and OCR text.
    """

    filename = Path(file.filename or "").name

    if not filename:
        raise HTTPException(
            status_code=400,
            detail="Filename is required.",
        )

    if Path(filename).suffix.lower() != ".pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported.",
        )

    document_id = str(uuid4())

    saved_path = None

    try:
        saved_path, file_size = save_uploaded_pdf(
            file,
            document_id,
        )

        # Validate the uploaded PDF and count pages.
        # Opening bytes avoids a leaked Windows file handle on malformed PDFs.
        with pymupdf.open(stream=saved_path.read_bytes(), filetype="pdf") as pdf:
            page_count = len(pdf)

        # Extract all supported evidence.
        storage_root = get_storage_root()

        image_directory = (
            storage_root
            / "images"
            / document_id
        )

        evidence = extract_pdf_evidence(
            pdf_path=saved_path,
            output_dir=image_directory,
            document_id=document_id,
            enable_ocr=True,
        )

        # Convert absolute image paths to storage-relative paths.
        for item in evidence:
            item.source = filename

            if item.file_path:

                item.file_path = Path(
                    item.file_path
                ).resolve().relative_to(
                    storage_root.resolve()
                ).as_posix()

        modality_counts = dict(
            Counter(
                item.modality
                for item in evidence
            )
        )

        document = DocumentRecord(
            document_id=document_id,
            filename=filename,
            status="completed",
            created_at=datetime.now(timezone.utc),
            page_count=page_count,
            evidence_count=len(evidence),
            file_size_bytes=file_size,
            storage_path=f"uploads/{document_id}.pdf",
            modality_counts=modality_counts,
        )

        # Persist document metadata and evidence.
        save_document_data(
            document,
            evidence,
            chunk_evidence(evidence),
        )

        return document

    except ValueError as exc:
        delete_document_data(document_id)

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception as exc:
        delete_document_data(document_id)

        raise HTTPException(
            status_code=422,
            detail=f"PDF processing failed: {str(exc)}",
        )

    finally:
        file.file.close()


@router.get(
    "",
    response_model=list[DocumentRecord],
)
def get_documents():
    """Return all uploaded documents."""

    return list_documents()


@router.get(
    "/{document_id}",
    response_model=DocumentRecord,
)
def get_document_details(
    document_id: str,
):
    """Return information about one document."""

    try:
        document = get_document(document_id)

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid document ID.",
        )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    return document



@router.get("/{document_id}/evidence")
def get_document_evidence_route(
    document_id: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    """Return extracted evidence with pagination."""

    try:
        # Storage already returns a list of dictionaries.
        evidence = get_document_evidence(document_id)

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid document ID.",
        )

    # Check whether the document exists.
    document = get_document(document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    # Apply pagination.
    total = len(evidence)
    paginated_evidence = evidence[skip: skip + limit]

    return {
        "document_id": document_id,
        "total": total,
        "skip": skip,
        "limit": limit,
        "evidence": paginated_evidence,
    }



@router.get("/{document_id}/chunks")
def get_document_chunks_route(
    document_id: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    """Inspect retrieval chunks; older uploads are prepared on demand."""
    get_document_details(document_id)
    chunks = get_document_chunks(document_id)
    if not chunks:
        evidence = [EvidenceUnit.model_validate(item) for item in get_document_evidence(document_id)]
        chunks = [item.model_dump(mode="json") for item in chunk_evidence(evidence)]
    return {
        "document_id": document_id,
        "total": len(chunks),
        "skip": skip,
        "limit": limit,
        "chunks": chunks[skip:skip + limit],
    }


@router.delete(
    "/{document_id}",
)
def delete_document(
    document_id: str,
):
    """Delete an uploaded document and its extracted data."""

    try:
        from omnirag.ingestion.indexer import index_lock
        from omnirag.vectorstore.qdrant_store import remove_document
        get_document_details(document_id)
        with index_lock:
            if (get_storage_root() / "index" / f"{document_id}.json").exists():
                remove_document(document_id)
            deleted = delete_document_data(document_id)

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid document ID.",
        )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    return {
        "message": "Document deleted successfully.",
        "document_id": document_id,
    }
