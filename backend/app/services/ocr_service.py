from functools import lru_cache
from pathlib import Path

import numpy as np
import pymupdf as fitz
from PIL import Image


@lru_cache(maxsize=1)
def _get_ocr_engine():
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


def _recognize_image(image: np.ndarray) -> str:
    result, _ = _get_ocr_engine()(image)
    if not result:
        return ""
    return "\n".join(text.strip() for _, text, _ in result if text.strip())


def _recognize_pdf_page(page: fitz.Page) -> str:
    pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
    rgb_image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
        pixmap.height, pixmap.width, pixmap.n
    )
    bgr_image = rgb_image[:, :, ::-1].copy()
    return _recognize_image(bgr_image)


def extract_text(file_path: Path) -> str:
    """Return recognized text; this does not extract structured invoice fields."""
    extension = file_path.suffix.lower()
    if extension == ".pdf":
        page_texts: list[str] = []
        with fitz.open(file_path) as document:
            for page in document:
                page_text = page.get_text("text").strip()
                if not page_text:
                    page_text = _recognize_pdf_page(page)
                if page_text:
                    page_texts.append(page_text)
        return "\n\n".join(page_texts)

    if extension in {".png", ".jpg", ".jpeg"}:
        with Image.open(file_path) as image:
            rgb_image = np.asarray(image.convert("RGB"))
        return _recognize_image(rgb_image[:, :, ::-1].copy())

    raise ValueError(f"Unsupported OCR file type: {extension}")