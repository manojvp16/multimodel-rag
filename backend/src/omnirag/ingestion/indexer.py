from threading import RLock

from omnirag.embeddings.gemini_embedder import GeminiEmbedder
from omnirag.ingestion.chunker import chunk_evidence
from omnirag.schemas.evidence import EvidenceUnit
from omnirag.storage import file_storage as storage
from omnirag.vectorstore import qdrant_store as store

# Serialize index/delete/search so partial replacements cannot be retrieved.
index_lock = RLock()


def index_document(document_id):
    with index_lock:
        if storage.get_document(document_id) is None:
            raise ValueError("Document not found.")
        state_path = storage.get_storage_root() / "index" / f"{document_id}.json"
        storage._write_json(state_path, {"status": "indexing"})
        try:
            embedder = GeminiEmbedder()
            evidence = [EvidenceUnit.model_validate(x) for x in storage.get_document_evidence(document_id)]
            chunks = chunk_evidence(evidence)
            for item in evidence:
                if item.modality == "image" and item.file_path:
                    from omnirag.schemas.chunk import RetrievalChunk
                    from uuid import uuid5, NAMESPACE_URL
                    root = storage.get_storage_root().resolve()
                    path = (root / item.file_path).resolve()
                    if not path.is_relative_to(root / "images" / document_id):
                        raise ValueError("Invalid image storage path.")
                    caption = embedder.caption(path)
                    chunks.append(RetrievalChunk(**{**item.model_dump(), "id": str(uuid5(NAMESPACE_URL, item.id + ':caption')),
                        "content": caption, "metadata": {**item.metadata, "representation": "generated_caption"}},
                        evidence_id=item.id, chunk_index=0, char_start=0, char_end=len(caption)))
            if not chunks:
                raise ValueError("No searchable content was extracted.")
            vectors = embedder.embed([x.content for x in chunks])
            store.remove_document(document_id)
            store.upsert(chunks, vectors)
            state = {"status": "indexed", "chunk_count": len(chunks), "collection": store.collection_name()}
            storage._write_json(state_path, state)
            return state
        except Exception:
            storage._write_json(state_path, {"status": "failed", "message": "Indexing failed. Check provider configuration and retry."})
            raise
