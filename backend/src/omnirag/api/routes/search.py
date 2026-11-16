import logging
from uuid import uuid4
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from omnirag.api.routes.documents import get_document_details
from omnirag.ingestion.indexer import index_document
from omnirag.rag.pipeline import answer_question
from omnirag.retrieval.retriever import search
from omnirag.schemas.search import SearchRequest
from omnirag.storage import file_storage as storage
from omnirag.storage.index_state import read_index_state
from omnirag.providers.reliability import ProviderFailure

router = APIRouter(prefix="/api/v1", tags=["Retrieval"])
logger = logging.getLogger(__name__)


def provider_error(exc: ProviderFailure):
    headers = {"Retry-After": str(max(1, int(exc.retry_after)))} if exc.retry_after else None
    return JSONResponse(status_code=exc.status, headers=headers, content={
        "detail": str(exc), "error_code": exc.code, "retryable": exc.retryable,
        "reference": exc.reference, "operation": exc.operation, "attempts": exc.attempts,
    })


def backend_error(operation):
    reference = uuid4().hex[:12]
    logger.exception('Backend failure reference=%s operation=%s', reference, operation)
    return JSONResponse(status_code=503, content={
        'detail': 'The backend could not complete this request. Check the server log using the error reference.',
        'error_code': 'backend_error', 'reference': reference, 'operation': operation, 'retryable': False,
    })


@router.post("/documents/{document_id}/index")
def index_route(document_id: str):
    get_document_details(document_id)
    try:
        return index_document(document_id)
    except ProviderFailure as exc:
        return provider_error(exc)
    except Exception:
        return backend_error('document_indexing')


@router.get("/documents/{document_id}/index")
def index_status(document_id: str):
    get_document_details(document_id)
    return read_index_state(document_id)


@router.get("/documents/{document_id}/file")
def document_file(document_id: str):
    document = get_document_details(document_id)
    path = storage.get_storage_root() / "uploads" / f"{document_id}.pdf"
    if not path.is_file():
        raise HTTPException(404, "PDF file not found.")
    return FileResponse(path, media_type="application/pdf", filename=document["filename"], content_disposition_type="inline")


@router.get("/documents/{document_id}/media/{evidence_id}")
def evidence_media(document_id: str, evidence_id: str):
    get_document_details(document_id)
    for item in storage.get_document_evidence(document_id):
        if item["id"] == evidence_id and item.get("file_path"):
            root = storage.get_storage_root().resolve()
            path = (root / item["file_path"]).resolve()
            if path.is_relative_to(root / "images" / document_id) and path.is_file():
                return FileResponse(path)
    raise HTTPException(404, "Media not found.")


@router.post("/search")
def search_route(request: SearchRequest):
    try:
        return {"results": search(request)}
    except ProviderFailure as exc:
        return provider_error(exc)
    except Exception:
        return backend_error('search')


@router.post("/chat")
def chat_route(request: SearchRequest):
    try:
        return answer_question(request)
    except ProviderFailure as exc:
        return provider_error(exc)
    except Exception:
        return backend_error('chat')
