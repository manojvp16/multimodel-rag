
from pathlib import Path
import os
from shutil import which

from PIL import Image
import pytesseract
from pytesseract import Output


# Configure Tesseract executable on Windows.
TESSERACT_PATH = Path(
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

def _configure_tesseract() -> None:
    """Resolve OCR only when needed, so digital PDFs work without Tesseract."""
    executable = os.environ.get("TESSERACT_CMD") or which("tesseract")
    if not executable and TESSERACT_PATH.exists():
        executable = str(TESSERACT_PATH)
    if not executable:
        raise RuntimeError("OCR requires Tesseract. Install it or set TESSERACT_CMD.")
    pytesseract.pytesseract.tesseract_cmd = executable


def extract_text_from_image(
    image: Image.Image,
    language: str = "eng",
) -> dict:
    """
    Extract text from an image using Tesseract OCR.
    """

    _configure_tesseract()
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    result = pytesseract.image_to_data(
        image,
        lang=language,
        output_type=Output.DICT,
    )

    words = []
    confidence_scores = []

    for index, word in enumerate(result["text"]):

        word = word.strip()

        try:
            confidence = float(result["conf"][index])
        except (ValueError, TypeError):
            continue

        if word and confidence >= 0:
            words.append(word)
            confidence_scores.append(confidence)

    extracted_text = " ".join(words).strip()

    average_confidence = (
        sum(confidence_scores) / len(confidence_scores)
        if confidence_scores
        else 0.0
    )

    return {
        "text": extracted_text,
        "confidence": round(average_confidence, 2),
        "word_count": len(words),
        "language": language,
        "extraction_method": "tesseract",
    }
