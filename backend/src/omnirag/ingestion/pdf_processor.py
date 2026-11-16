from pathlib import Path
from uuid import uuid4
from typing import Union
from io import BytesIO

import pymupdf
from PIL import Image

from omnirag.schemas.evidence import EvidenceUnit
from omnirag.extraction.ocr_extractor import extract_text_from_image


PathLike = Union[str, Path]


def _validate_pdf(pdf_path: PathLike) -> Path:
    """Validate the PDF input path."""

    pdf_file = Path(pdf_path)

    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    if not pdf_file.is_file():
        raise ValueError("The provided path is not a file.")

    if pdf_file.suffix.lower() != ".pdf":
        raise ValueError("Only PDF files are supported.")

    return pdf_file


def extract_pdf_text(pdf_path: PathLike) -> list[EvidenceUnit]:
    """
    Extract text from every page of a PDF.

    Maintains compatibility with the original function.
    Returns one EvidenceUnit for each page containing text.
    """

    pdf_file = _validate_pdf(pdf_path)
    document_id = str(uuid4())

    evidence_units = []

    with pymupdf.open(pdf_file) as pdf:

        for page_index, page in enumerate(pdf):

            page_text = page.get_text("text").strip()

            if not page_text:
                continue

            evidence = EvidenceUnit(
                document_id=document_id,
                source=pdf_file.name,
                page_number=page_index + 1,
                modality="text",
                content=page_text,
                metadata={
                    "extraction_method": "pymupdf",
                    "page_width": page.rect.width,
                    "page_height": page.rect.height,
                },
            )

            evidence_units.append(evidence)

    return evidence_units


def _extract_page_text(
    page,
    document_id: str,
    source: str,
    page_number: int,
) -> list[EvidenceUnit]:
    """Extract text evidence from one PDF page."""

    page_text = page.get_text("text").strip()

    if not page_text:
        return []

    return [
        EvidenceUnit(
            document_id=document_id,
            source=source,
            page_number=page_number,
            modality="text",
            content=page_text,
            metadata={
                "extraction_method": "pymupdf",
                "page_width": page.rect.width,
                "page_height": page.rect.height,
            },
        )
    ]


def _extract_page_images(
    pdf,
    page,
    document_id: str,
    source: str,
    page_number: int,
    image_dir: Path,
) -> list[EvidenceUnit]:
    """Extract embedded images from one PDF page."""

    evidence_units = []
    seen_xrefs = set()

    for image_index, image_info in enumerate(
        page.get_images(full=True)
    ):

        xref = image_info[0]

        # Ignore invalid and duplicate image references.
        if xref <= 0 or xref in seen_xrefs:
            continue

        seen_xrefs.add(xref)

        image_data = pdf.extract_image(xref)

        if not image_data:
            continue

        image_bytes = image_data["image"]
        image_extension = image_data["ext"]

        image_dir.mkdir(parents=True, exist_ok=True)

        image_filename = (
            f"{document_id}_page_{page_number}_"
            f"image_{image_index + 1}.{image_extension}"
        )

        image_path = image_dir / image_filename
        image_path.write_bytes(image_bytes)

        image_rects = page.get_image_rects(xref)

        evidence = EvidenceUnit(
            document_id=document_id,
            source=source,
            page_number=page_number,
            modality="image",
            content="",
            file_path=str(image_path.resolve()),
            metadata={
                "extraction_method": "pymupdf",
                "image_xref": xref,
                "image_index": image_index + 1,
                "width": image_data.get("width"),
                "height": image_data.get("height"),
                "extension": image_extension,
                "occurrence_rects": [
                    list(rect) for rect in image_rects
                ],
            },
        )

        evidence_units.append(evidence)

    return evidence_units


def _extract_page_tables(
    page,
    document_id: str,
    source: str,
    page_number: int,
) -> list[EvidenceUnit]:
    """Extract tables from one PDF page."""

    if not hasattr(page, "find_tables"):
        raise RuntimeError(
            "Your PyMuPDF version does not support table extraction. "
            "Upgrade PyMuPDF before continuing."
        )

    evidence_units = []

    table_finder = page.find_tables()

    for table_index, table in enumerate(table_finder.tables):

        rows = table.extract()

        if not rows:
            continue

        # Convert table rows into readable text.
        table_content = "\n".join(
            "\t".join(
                "" if cell is None else str(cell).strip()
                for cell in row
            )
            for row in rows
        ).strip()

        if not table_content:
            continue

        evidence = EvidenceUnit(
            document_id=document_id,
            source=source,
            page_number=page_number,
            modality="table",
            content=table_content,
            metadata={
                "extraction_method": "pymupdf",
                "table_index": table_index + 1,
                "row_count": len(rows),
                "column_count": max(
                    (len(row) for row in rows),
                    default=0,
                ),
                "bbox": list(table.bbox),
            },
        )

        evidence_units.append(evidence)

    return evidence_units


def _extract_page_ocr(
    page,
    document_id: str,
    source: str,
    page_number: int,
    language: str = "eng",
    dpi: int = 200,
) -> list[EvidenceUnit]:
    """
    Render a PDF page as an image and extract text using Tesseract OCR.
    """

    if dpi < 72 or dpi > 600:
        raise ValueError("OCR DPI must be between 72 and 600.")

    # Render PDF page into an image.
    pixmap = page.get_pixmap(
        dpi=dpi,
        alpha=False,
    )

    image_bytes = pixmap.tobytes("png")

    with Image.open(BytesIO(image_bytes)) as image:
        ocr_result = extract_text_from_image(
            image,
            language=language,
        )

    extracted_text = ocr_result["text"].strip()

    if not extracted_text:
        return []

    return [
        EvidenceUnit(
            document_id=document_id,
            source=source,
            modality="text",
            content=extracted_text,
            page_number=page_number,
            metadata={
                "extraction_method": "tesseract",
                "ocr_confidence": ocr_result["confidence"],
                "word_count": ocr_result["word_count"],
                "language": ocr_result["language"],
                "ocr_dpi": dpi,
            },
        )
    ]


def extract_pdf_evidence(
    pdf_path: PathLike,
    output_dir: PathLike | None = None,
    document_id: str | None = None,
    enable_ocr: bool = True,
    ocr_language: str = "eng",
    ocr_dpi: int = 200,
) -> list[EvidenceUnit]:
    """
    Extract digital text, OCR text, embedded images and tables
    from every page of a PDF.

    OCR is used as a fallback when digital text is unavailable.
    """

    pdf_file = _validate_pdf(pdf_path)

    document_id = document_id or str(uuid4())

    if output_dir is None:
        backend_root = Path(__file__).resolve().parents[3]
        image_dir = backend_root / "storage" / "images"
    else:
        image_dir = Path(output_dir)

    evidence_units: list[EvidenceUnit] = []

    with pymupdf.open(pdf_file) as pdf:

        for page_index, page in enumerate(pdf):

            page_number = page_index + 1

            # 1. Extract digitally available text.
            text_evidence = _extract_page_text(
                page,
                document_id,
                pdf_file.name,
                page_number,
            )

            evidence_units.extend(text_evidence)

            # 2. Use OCR if the page contains no digital text.
            if not text_evidence and enable_ocr:

                ocr_evidence = _extract_page_ocr(
                    page=page,
                    document_id=document_id,
                    source=pdf_file.name,
                    page_number=page_number,
                    language=ocr_language,
                    dpi=ocr_dpi,
                )

                evidence_units.extend(ocr_evidence)

            # 3. Extract embedded images.
            image_evidence = _extract_page_images(
                pdf,
                page,
                document_id,
                pdf_file.name,
                page_number,
                image_dir,
            )

            evidence_units.extend(image_evidence)

            # 4. Extract tables.
            table_evidence = _extract_page_tables(
                page,
                document_id,
                pdf_file.name,
                page_number,
            )

            evidence_units.extend(table_evidence)

    return evidence_units
