from omnirag.embeddings.gemini_embedder import GeminiEmbedder
from omnirag.ingestion.indexer import index_lock
from omnirag.storage.index_state import ready_document_ids
from omnirag.storage.file_storage import get_document_evidence
from omnirag.retrieval.excerpts import readable_excerpt
from omnirag.vectorstore import qdrant_store as store


def search(request):
    with index_lock:
        ids = ready_document_ids(request.document_ids)
        if not ids:
            return []
        vector = GeminiEmbedder().embed([request.question], query=True)[0]
        client = store.ensure_collection()
        hits = client.query_points(store.collection_name(), query=vector,
            query_filter=store.document_filter(ids), limit=request.top_k * 3,
            score_threshold=request.score_threshold).points
        results, seen, evidence_by_document = [], set(), {}
        for hit in hits:
            payload = hit.payload
            # Distinct chunks from the same page may contain different answers.
            key = (payload["document_id"], payload["content"].strip())
            if key in seen:
                continue
            seen.add(key)
            document_id = payload["document_id"]
            if document_id not in evidence_by_document:
                evidence_by_document[document_id] = {item["id"]: item for item in get_document_evidence(document_id)}
            evidence = evidence_by_document[document_id].get(payload["evidence_id"])
            results.append({"score": hit.score, "chunk": payload, "excerpt": readable_excerpt(payload, evidence)})
            if len(results) >= request.top_k:
                break
        return results
