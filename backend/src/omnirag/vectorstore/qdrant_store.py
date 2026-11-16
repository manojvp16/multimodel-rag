from functools import lru_cache
from hashlib import sha256

from qdrant_client import QdrantClient, models

from omnirag.config import settings
from omnirag.storage import file_storage as storage


def collection_name():
    signature = f"{settings.GEMINI_EMBEDDING_MODEL}:{settings.EMBEDDING_DIMENSIONS}"
    return settings.QDRANT_COLLECTION + "_" + sha256(signature.encode()).hexdigest()[:12]


@lru_cache
def get_client():
    if settings.QDRANT_LOCAL:
        return QdrantClient(path=str(storage.get_storage_root() / "qdrant"))
    return QdrantClient(url=settings.QDRANT_URL, timeout=30)


def ensure_collection():
    client = get_client()
    name = collection_name()
    if not client.collection_exists(name):
        client.create_collection(name, vectors_config=models.VectorParams(
            size=settings.EMBEDDING_DIMENSIONS, distance=models.Distance.COSINE))
    return client


def document_filter(ids):
    return models.Filter(must=[models.FieldCondition(key="document_id", match=models.MatchAny(any=ids))])


def remove_document(document_id):
    client = get_client()
    if client.collection_exists(collection_name()):
        client.delete(collection_name(), models.FilterSelector(filter=document_filter([document_id])), wait=True)


def upsert(chunks, vectors):
    client = ensure_collection()
    for start in range(0, len(chunks), 64):
        client.upsert(collection_name(), points=[models.PointStruct(
            id=chunk.id, vector=vector, payload=chunk.model_dump(mode="json"))
            for chunk, vector in zip(chunks[start:start + 64], vectors[start:start + 64], strict=True)], wait=True)
