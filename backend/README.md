# OmniRAG

A local PDF assistant with text/table extraction, OCR, image captions, Gemini embeddings, persistent Qdrant search, and answers with source citations. The responsive React frontend is built with Vite and served by FastAPI at `/`.

## Run

From the repository root in PowerShell:

```powershell
cd frontend
npm.cmd install
npm.cmd run build
cd ..
cd backend
# Existing environment:
.venv/Scripts/python.exe -m uvicorn omnirag.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. Upload a PDF, click **Index**, then ask a question. Select documents to narrow search; no selection searches all indexed documents. Upload and indexing are separate operations so provider failures can be retried without uploading again. Existing uploads can be indexed from the library.

For a fresh environment, install Python 3.12+ and uv, run `uv sync` from `backend/`, and copy `.env.example` to `.env`. Set `GEMINI_API_KEY` before indexing. API startup and digital PDF extraction work without a key. Development tests additionally need `uv pip install pytest httpx`.

## Configuration

`backend/.env` is loaded independently of the working directory. Environment variables override it.

| Variable | Default / purpose |
| --- | --- |
| GEMINI_API_KEY | Required for indexing and model calls |
| GEMINI_EMBEDDING_MODEL | gemini-embedding-2 |
| GEMINI_CHAT_MODEL | gemini-2.5-flash |
| EMBEDDING_DIMENSIONS | 768 |
| QDRANT_LOCAL | true: persistent embedded Qdrant, no Docker required |
| QDRANT_URL | http://localhost:6333, used when QDRANT_LOCAL=false |
| QDRANT_COLLECTION | omnirag_collection; model/dimension signature appended automatically |

For remote Qdrant run `docker compose up -d qdrant` from the repository root and set `QDRANT_LOCAL=false`. Reindex documents after changing embedding models or dimensions. Embedded Qdrant supports one application process; do not use multiple Uvicorn workers. API `/health` reports configuration, not provider connectivity.

OCR requires Tesseract on PATH, at the recognized Windows installation path, or configured with the process environment variable `TESSERACT_CMD`. Digital text PDFs do not require it. Provider model availability and quota depend on your account. Indexing sends extracted document text and embedded images to Gemini.

## Behavior and scope

- PDF uploads up to 50 MB; local files remain under `backend/storage/`.
- Text and tables are split into overlapping, source-linked chunks.
- Embedded images are described by the chat model and their captions are embedded for retrieval. This is caption-based visual retrieval, not direct image embeddings. Captions can be imperfect; original images are accessible from citations. Vector-drawn diagrams are not captured as embedded images.
- Search uses cosine similarity with a configurable request threshold (default 0.25), document filtering and evidence deduplication.
- Distinct chunks from the same page remain available for retrieval. Index status reports `needs_reindex` when embedding settings change. Chat distinguishes unindexed documents from indexed documents without matching evidence.
- Answers use bounded retrieved context and structured source IDs. Unknown citation IDs are rejected. Unsupported questions have an insufficient-evidence response. Citation validation checks identity, not factual entailment; verify important claims against the original page.
- Index state is persisted; failed/interrupted indexes are excluded from retrieval until successfully retried. Reindex replaces existing vectors. Delete removes vectors before local artifacts.
- Operations are synchronous and serialized around indexing/search/deletion. This local single-user application has no authentication or durable background job queue; keep its default loopback binding. Audio and video ingestion are outside this PDF project's scope.

## API

Interactive API documentation: `/docs`.

- `POST /api/v1/documents/upload` multipart `file`
- `GET /api/v1/documents`
- `GET /api/v1/documents/{id}`
- `GET /api/v1/documents/{id}/evidence` and `/chunks` (paginated)
- `POST /api/v1/documents/{id}/index`, `GET` same path for status
- `GET /api/v1/documents/{id}/file`
- `GET /api/v1/documents/{id}/media/{evidence_id}`
- `DELETE /api/v1/documents/{id}`
- `POST /api/v1/search` and `/api/v1/chat`

Search/chat body:

```json
{"question":"What are the main findings?","document_ids":[],"top_k":5,"score_threshold":0.25}
```

## Verify

From the repository root:

```powershell
backend/.venv/Scripts/python.exe -m pytest backend/tests -q -p no:cacheprovider --basetemp=backend/.test-tmp-check
cd frontend
npm.cmd run build
```

Tests cover extraction, chunking, storage cleanup, HTTP upload/index/search/chat/delete, document isolation, idempotent reindex, failed-index retry, invalid input and citation IDs. HTTP RAG tests use real in-memory Qdrant with a fake Gemini provider, so they do not establish live model quality, remote Qdrant connectivity or actual OCR recognition. Browser rendering needs a manual check.

Implementation references: [Gemini embeddings](https://ai.google.dev/gemini-api/docs/embeddings) and [Qdrant Python client](https://github.com/qdrant/qdrant-client).

Frontend development uses `npm.cmd run dev` in `frontend/` alongside FastAPI on port 8000. The Vite server on http://127.0.0.1:5173 proxies API and documentation requests. Rebuild after frontend changes before serving through FastAPI. If the build is missing, `/` returns HTTP 503 with setup instructions; API endpoints remain available.

## Intermittent provider failures

Each question embeds its query and then generates a structured answer. Either Gemini call can fail independently. Temporary rate limits, service errors and network timeouts receive up to three attempts with exponential backoff and jitter. Empty or malformed structured answers receive one regeneration attempt. Access/configuration errors fail immediately. Long `Retry-After` delays are returned to the caller rather than retried prematurely. SDK retries are disabled to keep this application retry budget bounded; individual HTTP calls time out after 30 seconds.

Errors include a safe `error_code`, `operation`, `retryable` flag, and reference matching the server log. Provider errors also include the attempt count. The frontend displays the specific message and offers **Retry question** for retryable failures, preserving the original document selection and response mode. Exhausted quota still requires waiting or checking your Gemini account; automatic retries cannot guarantee success. The log's operation distinguishes query embedding, answer generation and image caption failures. Unexpected backend errors have a separate reference and full server traceback.
