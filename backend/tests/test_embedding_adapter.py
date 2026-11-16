from types import SimpleNamespace
import pytest

from omnirag.config import settings
from omnirag.embeddings.gemini_embedder import GeminiEmbedder


def test_embedding_batching_and_task_types(monkeypatch):
    monkeypatch.setattr(settings, 'EMBEDDING_DIMENSIONS', 3)
    monkeypatch.setattr(settings, 'GEMINI_EMBEDDING_MODEL', 'gemini-embedding-001')
    calls = []
    def embed_content(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(embeddings=[SimpleNamespace(values=[1., 0., 0.]) for _ in kwargs['contents']])
    adapter = GeminiEmbedder.__new__(GeminiEmbedder)
    adapter.client = SimpleNamespace(models=SimpleNamespace(embed_content=embed_content))
    assert len(adapter.embed(['text'] * 33)) == 33
    assert len(calls) == 2
    assert calls[0]['config'].task_type == 'RETRIEVAL_DOCUMENT'
    adapter.embed(['question'], query=True)
    assert calls[-1]['config'].task_type == 'RETRIEVAL_QUERY'
    monkeypatch.setattr(settings, 'GEMINI_EMBEDDING_MODEL', 'gemini-embedding-2')
    adapter.embed(['first', 'second'])
    assert calls[-1]['config'].task_type is None
    assert calls[-1]['contents'][0].parts[0].text == 'title: none | text: first'
    assert len(calls[-1]['contents']) == 2
    adapter.embed(['question'], query=True)
    assert calls[-1]['contents'][0].parts[0].text == 'task: search result | query: question'


@pytest.mark.parametrize('values', [[1.], [float('nan'), 0., 1.]])
def test_bad_vectors_rejected(monkeypatch, values):
    monkeypatch.setattr(settings, 'EMBEDDING_DIMENSIONS', 3)
    adapter = GeminiEmbedder.__new__(GeminiEmbedder)
    adapter.client = SimpleNamespace(models=SimpleNamespace(embed_content=lambda **kwargs:
        SimpleNamespace(embeddings=[SimpleNamespace(values=values)])))
    with pytest.raises(RuntimeError):
        adapter.embed(['text'])
