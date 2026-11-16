"""Gemini text embeddings and explicit image-to-caption preparation."""
import math
import mimetypes
from pathlib import Path

from google import genai
from google.genai import types

from omnirag.config import settings
from omnirag.providers.reliability import call_provider


class GeminiEmbedder:
    def __init__(self):
        if not settings.GEMINI_API_KEY:
            raise RuntimeError("Configure GEMINI_API_KEY in backend/.env before indexing or chatting.")
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY,
                                  http_options=types.HttpOptions(timeout=30000,
                                      retry_options=types.HttpRetryOptions(attempts=1)))

    def embed(self, texts: list[str], query: bool = False) -> list[list[float]]:
        vectors = []
        for start in range(0, len(texts), 32):
            batch_texts = texts[start:start + 32]
            config = types.EmbedContentConfig(output_dimensionality=settings.EMBEDDING_DIMENSIONS)
            if "gemini-embedding-2" in settings.GEMINI_EMBEDDING_MODEL:
                # Embedding 2 aggregates bare strings and does not accept task_type.
                prefix = "task: search result | query: " if query else "title: none | text: "
                contents = [types.Content(parts=[types.Part.from_text(text=prefix + text)]) for text in batch_texts]
            else:
                contents = batch_texts
                config.task_type = "RETRIEVAL_QUERY" if query else "RETRIEVAL_DOCUMENT"
            response = call_provider('query_embedding' if query else 'document_embedding',
                lambda: self.client.models.embed_content(
                    model=settings.GEMINI_EMBEDDING_MODEL, contents=contents, config=config))
            batch = [item.values for item in response.embeddings or []]
            if len(batch) != len(texts[start:start + 32]):
                raise RuntimeError("Embedding provider returned an incomplete batch.")
            for vector in batch:
                if len(vector) != settings.EMBEDDING_DIMENSIONS or not all(math.isfinite(x) for x in vector):
                    raise RuntimeError("Embedding provider returned invalid dimensions or values.")
                vectors.append(vector)
        return vectors

    def caption(self, path: Path) -> str:
        response = call_provider('image_caption', lambda: self.client.models.generate_content(
            model=settings.GEMINI_CHAT_MODEL,
            contents=["Describe this document image for retrieval. Include visible labels, values, trends and relationships. Do not invent unreadable details.",
                      types.Part.from_bytes(data=path.read_bytes(), mime_type=mimetypes.guess_type(path.name)[0] or "image/png")]))
        if not response.text:
            raise RuntimeError("Image caption generation returned no content.")
        return response.text
