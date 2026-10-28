import subprocess
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Literal

import numpy as np
import pymupdf as fitz
from PIL import Image, UnidentifiedImageError


class OCRDocumentError(ValueError):
    """The provided path is missing, corrupt, or is not a supported document."""


@dataclass(frozen=True)
class OCRDocumentResult:
    text: str
    source: Literal["embedded_text", "rapidocr", "mixed", "empty"]
    token_confidences: list[float] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def mean_token_confidence(self) -> float | None:
        if not self.token_confidences:
            return None
        return sum(self.token_confidences) / len(self.token_confidences)


@lru_cache(maxsize=1)
def _is_ocr_engine_available() -> bool:
    """Check if the native ONNX runtime can be initialized without an OS access violation."""
    try:
        proc = subprocess.run(
            [sys.executable, "-c", "import onnxruntime; from rapidocr_onnxruntime import RapidOCR"],
            capture_output=True,
            timeout=5,
        )
        return proc.returncode == 0
    except Exception:
        return False


@lru_cache(maxsize=1)
def _get_ocr_engine():
    if not _is_ocr_engine_available():
        raise RuntimeError(
            "RapidOCR ONNX runtime is unavailable or crashed on this platform (native access violation)."
        )
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


def _recognize_image_with_confidence(image: np.ndarray) -> tuple[str, list[float]]:
    result, _ = _get_ocr_engine()(image)
    if not result:
        return "", []

    recognized: list[str] = []
    confidences: list[float] = []
    for detection in result:
        if len(detection) < 3:
            continue
        _, text, score = detection
        cleaned_text = text.strip()
        if not cleaned_text:
            continue
        recognized.append(cleaned_text)
        try:
            confidence = float(score)
        except (TypeError, ValueError):
            continue
        if 0.0 <= confidence <= 1.0:
            confidences.append(confidence)
    return "\n".join(recognized), confidences


def _recognize_image(image: np.ndarray) -> str:
    """Preserve the original text-only OCR helper used by existing callers."""
    return _recognize_image_with_confidence(image)[0]


def _recognize_pdf_page(
    page: fitz.Page, detailed: bool
) -> tuple[str, list[float]]:
    pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
    rgb_image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
        pixmap.height, pixmap.width, pixmap.n
    )
    bgr_image = rgb_image[:, :, ::-1].copy()
    if detailed:
        return _recognize_image_with_confidence(bgr_image)
    return _recognize_image(bgr_image), []


def _extract_document(file_path: Path, detailed: bool) -> OCRDocumentResult:
    extension = file_path.suffix.lower()
    if extension not in {".pdf", ".png", ".jpg", ".jpeg"}:
        raise OCRDocumentError(f"Unsupported OCR file type: {extension or '(none)'}")
    if not file_path.is_file():
        raise OCRDocumentError("The document does not exist or is not a file.")

    page_texts: list[str] = []
    token_confidences: list[float] = []
    sources: set[str] = set()
    warnings: list[str] = []

    if extension == ".pdf":
        try:
            document = fitz.open(file_path)
        except (fitz.FileDataError, fitz.EmptyFileError, OSError) as error:
            raise OCRDocumentError("The PDF is empty, corrupt, or unreadable.") from error

        with document:
            if document.page_count == 0:
                warnings.append("The PDF contains no pages.")
            for page_number, page in enumerate(document, start=1):
                try:
                    embedded_text = page.get_text("text").strip()
                except Exception:
                    warnings.append(f"Page {page_number} could not be read.")
                    continue
                if embedded_text:
                    page_texts.append(embedded_text)
                    sources.add("embedded_text")
                    continue
                try:
                    page_text, scores = _recognize_pdf_page(page, detailed)
                except Exception:
                    warnings.append(f"Page {page_number} could not be read by OCR.")
                    continue
                if page_text:
                    page_texts.append(page_text)
                    sources.add("rapidocr")
                    token_confidences.extend(scores)
                else:
                    warnings.append(f"Page {page_number} contained no readable text.")
    else:
        try:
            with Image.open(file_path) as image:
                rgb_image = np.asarray(image.convert("RGB"))
        except (
            UnidentifiedImageError,
            Image.DecompressionBombError,
            OSError,
            ValueError,
        ) as error:
            raise OCRDocumentError("The image is corrupt or unreadable.") from error
        bgr_image = rgb_image[:, :, ::-1].copy()
        try:
            if detailed:
                image_text, scores = _recognize_image_with_confidence(bgr_image)
            else:
                image_text, scores = _recognize_image(bgr_image), []
        except Exception:
            warnings.append("The image could not be read by OCR.")
        else:
            if image_text:
                page_texts.append(image_text)
                sources.add("rapidocr")
                token_confidences.extend(scores)
            else:
                warnings.append("The image contained no readable text.")

    text = "\n\n".join(page_texts)
    source: Literal["embedded_text", "rapidocr", "mixed", "empty"]
    if not sources:
        source = "empty"
    elif len(sources) > 1:
        source = "mixed"
    elif "embedded_text" in sources:
        source = "embedded_text"
    else:
        source = "rapidocr"
    return OCRDocumentResult(
        text=text,
        source=source,
        token_confidences=token_confidences,
        warnings=warnings,
    )


def extract_document(file_path: Path) -> OCRDocumentResult:
    """Extract document text and retain available RapidOCR token scores."""
    return _extract_document(file_path, detailed=True)


def extract_text(file_path: Path) -> str:
    """Return document text; preserve the legacy text-only API."""
    return _extract_document(file_path, detailed=False).text
