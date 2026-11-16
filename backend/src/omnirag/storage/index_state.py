"""Shared readiness rules for the API and retrieval."""
import json

from omnirag.storage import file_storage as storage
from omnirag.vectorstore.qdrant_store import collection_name


def read_index_state(document_id: str) -> dict:
    path = storage.get_storage_root() / "index" / f"{document_id}.json"
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"status": "not_indexed"}
    if state.get("status") == "indexed" and state.get("collection") != collection_name():
        return {**state, "status": "needs_reindex", "message": "Embedding settings changed. Reindex this document."}
    return state


def ready_document_ids(requested_ids=()) -> list[str]:
    requested = {str(value) for value in requested_ids}
    return [document["document_id"] for document in storage.list_documents()
            if (not requested or document["document_id"] in requested)
            and read_index_state(document["document_id"]).get("status") == "indexed"]
