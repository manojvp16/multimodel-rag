
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from contextlib import asynccontextmanager

from omnirag.config import settings
from omnirag.api.access import require_access, validate_deployment_settings

from omnirag.api.routes.documents import (
    router as documents_router,
)


@asynccontextmanager
async def lifespan(app):
    validate_deployment_settings()
    try:
        yield
    finally:
        from omnirag.vectorstore.qdrant_store import get_client
        if get_client.cache_info().currsize:
            get_client().close()
            get_client.cache_clear()


app = FastAPI(
    title=settings.APP_NAME,
    description="Multimodal Retrieval Augmented Generation System",
    version="1.0.0",
    lifespan=lifespan,
)
app.middleware('http')(require_access)


app.include_router(documents_router)
from omnirag.api.routes.search import router as search_router
app.include_router(search_router)
frontend = Path(__file__).resolve().parents[3] / "frontend" / "dist"
app.mount("/assets", StaticFiles(directory=frontend / "assets", check_dir=False), name="frontend")


@app.get("/")
async def home():
    if not (frontend / "index.html").is_file():
        raise HTTPException(503, "Frontend is not built. Run npm install and npm run build in frontend/, or use the Vite development server.")
    return FileResponse(frontend / "index.html")


@app.get("/health")
async def health():

    return {
        "status": "healthy",
        "application": settings.APP_NAME,
        "gemini_configured": bool(settings.GEMINI_API_KEY),
        "vector_storage": "local" if settings.QDRANT_LOCAL else "remote",
    }


def run():
    import uvicorn
    uvicorn.run("omnirag.main:app", host="127.0.0.1", port=8000)
