# Build React separately so Node and source packages stay out of the runtime.
FROM node:22-bookworm-slim AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/index.html frontend/style.css frontend/vite.config.js ./
COPY frontend/src ./src
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
COPY --from=ghcr.io/astral-sh/uv:0.12.9 /uv /usr/local/bin/uv
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app/backend
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    PYTHONPATH=/app/backend/src \
    PATH=/app/backend/.venv/bin:$PATH \
    STORAGE_DIR=/app/backend/storage \
    QDRANT_LOCAL=true \
    DEBUG=false
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/src ./src
COPY --from=frontend-build /build/frontend/dist /app/frontend/dist
RUN python -c "from omnirag.storage.file_storage import get_storage_root; from omnirag.main import app; assert app.title; print('Backend import check passed')"
RUN mkdir -p /app/backend/storage
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/health',timeout=4)"
CMD ["sh", "-c", "exec uvicorn omnirag.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
