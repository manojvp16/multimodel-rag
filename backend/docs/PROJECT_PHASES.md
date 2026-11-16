# Implemented project phases

The original ingestion foundation has been extended through the complete local PDF question-answering flow. See [the backend README](../README.md) for current setup, contracts, verification and limitations.

| Phase | Implementation |
| --- | --- |
| Foundation | FastAPI, optional-at-startup Gemini settings, fixed CLI entry point |
| Extraction | PDF digital text, tables, embedded images and optional Tesseract OCR |
| Persistence | Uploads, evidence, chunks, metadata and full document cleanup |
| Preparation | Deterministic overlapping text/table chunks with provenance |
| Embeddings | Gemini batched embeddings with dimension/value validation; generated image captions |
| Indexing | Persistent local or remote Qdrant, model-specific collections, retryable state, idempotent replacement |
| Retrieval | Query embeddings, similarity threshold, document filters, evidence deduplication |
| Answers | Bounded source context, structured output, validated citation identity, insufficient-evidence path |
| Interface | Responsive library, upload, indexing status/retry, document selection, search/chat, PDF and image citations, deletion |
| Validation | Unit and HTTP lifecycle tests using real in-memory Qdrant and a deterministic Gemini fake |

Live Gemini, remote Qdrant, browser rendering and OCR recognition require environment-specific verification. Caption search does not interpret PDF vector drawings. The application runs as a local single-user process; authentication, audio/video ingestion and durable background workers are outside this scope.
