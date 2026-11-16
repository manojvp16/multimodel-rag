
import json
from pathlib import Path
from uuid import UUID
from typing import Any

from fastapi import UploadFile

MAX_UPLOAD_SIZE = 50 * 1024 * 1024


def get_storage_root() -> Path:
    """Return the backend/storage directory."""
    from omnirag.config import settings
    if settings.STORAGE_DIR is not None:
        return settings.STORAGE_DIR.expanduser().resolve()
    return Path(__file__).resolve().parents[3] / "storage"


def save_uploaded_pdf(
    upload: UploadFile,
    document_id: str,
) -> tuple[Path, int]:
    """Save an uploaded PDF and enforce the upload size limit."""
    UUID(document_id)

    if not upload.filename or Path(upload.filename).suffix.lower() != ".pdf":
        raise ValueError("Only PDF files are supported.")

    upload_dir = get_storage_root() / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    destination = upload_dir / f"{document_id}.pdf"
    total_size = 0

    try:
        with destination.open("wb") as output:
            while True:
                chunk = upload.file.read(1024 * 1024)
                if not chunk:
                    break

                total_size += len(chunk)

                if total_size > MAX_UPLOAD_SIZE:
                    raise ValueError("PDF exceeds the 50 MB upload limit.")

                output.write(chunk)

        if total_size == 0:
            raise ValueError("Uploaded PDF is empty.")

        return destination, total_size

    except Exception:
        destination.unlink(missing_ok=True)
        raise


def _write_json(destination: Path, data: Any) -> None:
    """Write JSON atomically to avoid incomplete files."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")

    try:
        temporary.write_text(
            json.dumps(data, indent=2, default=str),
            encoding="utf-8",
        )
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def save_document_data(document: Any, evidence: list[Any], chunks: list[Any] | None = None) -> None:
    """Persist document metadata and extracted evidence."""
    root = get_storage_root()
    document_id = document.document_id
    UUID(document_id)

    metadata_path = root / "metadata" / f"{document_id}.json"
    evidence_path = root / "evidence" / f"{document_id}.json"
    chunks_path = root / "chunks" / f"{document_id}.json"

    try:
        _write_json(metadata_path, document.model_dump(mode="json"))
        _write_json(
            evidence_path,
            [item.model_dump(mode="json") for item in evidence],
        )
        if chunks is not None:
            _write_json(chunks_path, [item.model_dump(mode="json") for item in chunks])
    except Exception:
        metadata_path.unlink(missing_ok=True)
        evidence_path.unlink(missing_ok=True)
        chunks_path.unlink(missing_ok=True)
        raise


def get_document(document_id: str) -> dict | None:
    UUID(document_id)

    path = get_storage_root() / "metadata" / f"{document_id}.json"

    if not path.exists():
        return None

    return json.loads(path.read_text(encoding="utf-8"))


def list_documents() -> list[dict]:
    metadata_dir = get_storage_root() / "metadata"

    if not metadata_dir.exists():
        return []

    documents = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in metadata_dir.glob("*.json")
    ]

    return sorted(
        documents,
        key=lambda item: item.get("created_at", ""),
        reverse=True,
    )


def get_document_evidence(document_id: str) -> list[dict]:
    UUID(document_id)

    path = get_storage_root() / "evidence" / f"{document_id}.json"

    if not path.exists():
        return []

    return json.loads(path.read_text(encoding="utf-8"))


def get_document_chunks(document_id: str) -> list[dict]:
    UUID(document_id)
    path = get_storage_root() / "chunks" / f"{document_id}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def delete_document_data(document_id: str) -> bool:
    """Delete a document and its locally stored extracted data."""
    UUID(document_id)

    root = get_storage_root()
    existed = (root / "metadata" / f"{document_id}.json").exists()

    (root / "uploads" / f"{document_id}.pdf").unlink(missing_ok=True)
    (root / "metadata" / f"{document_id}.json").unlink(missing_ok=True)
    (root / "evidence" / f"{document_id}.json").unlink(missing_ok=True)
    (root / "chunks" / f"{document_id}.json").unlink(missing_ok=True)
    (root / "index" / f"{document_id}.json").unlink(missing_ok=True)

    image_dir = root / "images" / document_id

    if image_dir.exists():
        import shutil
        shutil.rmtree(image_dir)

    return existed
