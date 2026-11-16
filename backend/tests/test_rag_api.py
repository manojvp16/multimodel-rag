from types import SimpleNamespace
import json

import pymupdf
import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from omnirag.config import settings
from omnirag.main import app
from omnirag.api.routes import documents
from omnirag.storage import file_storage as storage
from omnirag.ingestion import indexer
from omnirag.retrieval import retriever
from omnirag.rag import pipeline
from omnirag.vectorstore import qdrant_store


class FakeEmbedder:
    def embed(self, texts, query=False):
        return [[1.0, 0.0, 0.0] for _ in texts]

    @property
    def client(self):
        return SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kwargs:
            SimpleNamespace(text=json.dumps({"answer": "Revenue is 42 million.", "source_ids": [1]}))))


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "get_storage_root", lambda: tmp_path)
    monkeypatch.setattr(documents, "get_storage_root", lambda: tmp_path)
    monkeypatch.setattr(settings, "EMBEDDING_DIMENSIONS", 3)
    qdrant = QdrantClient(":memory:")
    from functools import lru_cache
    monkeypatch.setattr(qdrant_store, "get_client", lru_cache()(lambda: qdrant))
    for module in (indexer, retriever, pipeline):
        monkeypatch.setattr(module, "GeminiEmbedder", FakeEmbedder)
    with TestClient(app) as client:
        yield client
    qdrant.close()


def upload(client, filename="report.pdf"):
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((50, 50), "Revenue is 42 million.")
        data = pdf.tobytes()
    response = client.post('/api/v1/documents/upload', files={"file": (filename, data, "application/pdf")})
    assert response.status_code == 201
    return response.json()["document_id"]


def test_full_lifecycle(client):
    from omnirag.main import frontend
    if (frontend / 'index.html').exists():
        response = client.get('/')
        assert response.status_code == 200
        import re
        script = re.search(r'src="(/assets/[^\"]+\.js)"', response.text)
        assert script and client.get(script.group(1)).status_code == 200
    else:
        assert client.get('/').status_code == 503
    first, second = upload(client), upload(client, "other.pdf")
    for document_id in (first, second):
        assert client.post(f'/api/v1/documents/{document_id}/index').status_code == 200
    assert client.post(f'/api/v1/documents/{first}/index').status_code == 200
    assert qdrant_store.get_client().count(qdrant_store.collection_name()).count == 2
    request = {"question": "What is revenue?", "document_ids": [first]}
    hits = client.post('/api/v1/search', json=request).json()['results']
    assert len(hits) == 1 and hits[0]['chunk']['document_id'] == first
    answer = client.post('/api/v1/chat', json=request).json()
    assert answer['answer'] == 'Revenue is 42 million.'
    assert answer['citations'][0]['chunk']['document_id'] == first
    assert client.get(f'/api/v1/documents/{first}/file').headers['content-type'] == 'application/pdf'
    assert client.delete(f'/api/v1/documents/{first}').status_code == 200
    assert qdrant_store.get_client().count(qdrant_store.collection_name()).count == 1
    assert client.post('/api/v1/chat', json=request).json()['insufficient_evidence']
    assert client.delete(f'/api/v1/documents/{first}').status_code == 404


def test_validation_and_failure_retry(client, monkeypatch):
    for question in ('', '   '):
        assert client.post('/api/v1/chat', json={"question": question}).status_code == 422
    assert client.post('/api/v1/search', json={"question": "x", "document_ids": ["bad"]}).status_code == 422
    assert client.post('/api/v1/documents/upload', files={"file": ('bad.pdf', b'garbage')}).status_code == 422
    document_id = upload(client)
    class Broken(FakeEmbedder):
        def embed(self, *args, **kwargs):
            raise RuntimeError('provider failure')
    monkeypatch.setattr(indexer, 'GeminiEmbedder', Broken)
    assert client.post(f'/api/v1/documents/{document_id}/index').status_code == 503
    assert client.get(f'/api/v1/documents/{document_id}/index').json()['status'] == 'failed'
    assert client.post('/api/v1/search', json={"question": 'revenue'}).json()['results'] == []
    monkeypatch.setattr(indexer, 'GeminiEmbedder', FakeEmbedder)
    assert client.post(f'/api/v1/documents/{document_id}/index').status_code == 200


def test_invalid_generated_citation_is_rejected(client, monkeypatch):
    document_id = upload(client)
    client.post(f'/api/v1/documents/{document_id}/index')
    class BadCitation(FakeEmbedder):
        @property
        def client(self):
            return SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kwargs:
                SimpleNamespace(text='{"answer":"Unsupported","source_ids":[999]}')))
    monkeypatch.setattr(pipeline, 'GeminiEmbedder', BadCitation)
    result = client.post('/api/v1/chat', json={"question":"revenue"}).json()
    assert result['insufficient_evidence'] and result['citations'] == []


def test_image_caption_index_and_media(client, monkeypatch):
    from PIL import Image
    from io import BytesIO
    image = BytesIO()
    Image.new('RGB', (40, 40), 'red').save(image, format='PNG')
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((50, 50), 'A red chart')
        page.insert_image(pymupdf.Rect(50, 80, 150, 180), stream=image.getvalue())
        data = pdf.tobytes()
    response = client.post('/api/v1/documents/upload', files={'file': ('chart.pdf', data)})
    assert response.status_code == 201
    document_id = response.json()['document_id']
    monkeypatch.setattr(FakeEmbedder, 'caption', lambda self, path: 'A red chart image', raising=False)
    response = client.post(f'/api/v1/documents/{document_id}/index')
    assert response.status_code == 200 and response.json()['chunk_count'] == 2
    hits = client.post('/api/v1/search', json={'question':'chart'}).json()['results']
    visual = next(hit['chunk'] for hit in hits if hit['chunk']['modality'] == 'image')
    assert visual['metadata']['representation'] == 'generated_caption'
    media = client.get(f"/api/v1/documents/{document_id}/media/{visual['evidence_id']}")
    assert media.status_code == 200 and media.headers['content-type'] == 'image/png'


def test_unindexed_documents_explain_next_step(client):
    document_id = upload(client)
    response = client.post('/api/v1/chat', json={'question': 'revenue', 'document_ids': [document_id]})
    assert response.status_code == 200
    assert response.json()['reason'] == 'no_indexed_documents'
    assert 'Choose Index' in response.json()['answer']


def test_changed_embedding_settings_require_reindex(client, monkeypatch):
    document_id = upload(client)
    assert client.post(f'/api/v1/documents/{document_id}/index').status_code == 200
    monkeypatch.setattr(settings, 'GEMINI_EMBEDDING_MODEL', 'another-embedding-model')
    assert client.get(f'/api/v1/documents/{document_id}/index').json()['status'] == 'needs_reindex'
    response = client.post('/api/v1/chat', json={'question': 'revenue'})
    assert response.json()['reason'] == 'no_indexed_documents'


def test_different_chunks_from_same_evidence_are_retrieved(client):
    from uuid import uuid4
    from omnirag.schemas.chunk import RetrievalChunk
    document_id = upload(client)
    client.post(f'/api/v1/documents/{document_id}/index')
    existing = storage.get_document_chunks(document_id)[0]
    extra = RetrievalChunk.model_validate({**existing, 'id': str(uuid4()), 'content': 'A different detail on the same page', 'chunk_index': 1})
    qdrant_store.upsert([extra], [[1., 0., 0.]])
    hits = client.post('/api/v1/search', json={'question': 'revenue'}).json()['results']
    assert len(hits) == 2
    assert hits[0]['chunk']['evidence_id'] == hits[1]['chunk']['evidence_id']


def test_malformed_answer_recovers_without_new_user_question(client, monkeypatch):
    from omnirag.providers import reliability
    monkeypatch.setattr(reliability.time, 'sleep', lambda delay: None)
    document_id = upload(client)
    client.post(f'/api/v1/documents/{document_id}/index')
    outputs = iter(['not valid JSON', '{"answer":"Revenue is 42 million.","source_ids":[1]}'])
    class Recovering(FakeEmbedder):
        @property
        def client(self):
            return SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kwargs: SimpleNamespace(text=next(outputs))))
    monkeypatch.setattr(pipeline, 'GeminiEmbedder', Recovering)
    result = client.post('/api/v1/chat', json={'question':'revenue'})
    assert result.status_code == 200
    assert result.json()['answer'] == 'Revenue is 42 million.'
    assert len(result.json()['citations']) == 1


def test_persistent_rate_limit_returns_actionable_error(client, monkeypatch):
    from google.genai.errors import APIError
    from omnirag.providers import reliability
    monkeypatch.setattr(reliability.time, 'sleep', lambda delay: None)
    document_id = upload(client)
    client.post(f'/api/v1/documents/{document_id}/index')
    def fail(**kwargs):
        raise APIError(429, {'error': {'message': 'provider detail'}})
    class RateLimited(FakeEmbedder):
        @property
        def client(self):
            return SimpleNamespace(models=SimpleNamespace(generate_content=fail))
    monkeypatch.setattr(pipeline, 'GeminiEmbedder', RateLimited)
    response = client.post('/api/v1/chat', json={'question':'revenue'})
    assert response.status_code == 429
    result = response.json()
    assert result['error_code'] == 'provider_rate_limit'
    assert result['retryable'] and result['attempts'] == 3
    assert result['operation'] == 'answer_generation'
    assert len(result['reference']) == 12
    assert 'quota' in result['detail']


def test_persistent_invalid_output_is_reported_separately(client, monkeypatch):
    from omnirag.providers import reliability
    monkeypatch.setattr(reliability.time, 'sleep', lambda delay: None)
    document_id = upload(client)
    client.post(f'/api/v1/documents/{document_id}/index')
    class EmptyAnswer(FakeEmbedder):
        @property
        def client(self):
            return SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kwargs: SimpleNamespace(text='')))
    monkeypatch.setattr(pipeline, 'GeminiEmbedder', EmptyAnswer)
    response = client.post('/api/v1/chat', json={'question':'revenue'})
    assert response.status_code == 502
    assert response.json()['error_code'] == 'invalid_model_response'
    assert response.json()['attempts'] == 2
