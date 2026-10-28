import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pymupdf as fitz
from PIL import Image

from app.services import ocr_service
from app.services.ocr_service import OCRDocumentError


class OCRServiceTests(unittest.TestCase):
    def test_pdf_embedded_text_is_extracted_without_ocr(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pdf_path = Path(directory) / "text-invoice.pdf"
            document = fitz.open()
            page = document.new_page()
            page.insert_text((72, 72), "Invoice number: INV-200")
            document.save(pdf_path)
            document.close()

            with patch.object(ocr_service, "_recognize_image") as recognize_image:
                text = ocr_service.extract_text(pdf_path)

        self.assertIn("Invoice number: INV-200", text)
        recognize_image.assert_not_called()

    def test_scanned_pdf_page_uses_mocked_ocr(self) -> None:
        image_buffer = BytesIO()
        Image.new("RGB", (32, 24), "white").save(image_buffer, format="PNG")

        with tempfile.TemporaryDirectory() as directory:
            pdf_path = Path(directory) / "scanned-invoice.pdf"
            document = fitz.open()
            page = document.new_page()
            page.insert_image(page.rect, stream=image_buffer.getvalue())
            document.save(pdf_path)
            document.close()

            with patch.object(ocr_service, "_recognize_image", return_value="Scanned invoice text") as recognize_image:
                text = ocr_service.extract_text(pdf_path)

        self.assertEqual(text, "Scanned invoice text")
        recognize_image.assert_called_once()

    def test_png_and_jpeg_use_mocked_ocr(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            for extension, image_format in ((".png", "PNG"), (".jpg", "JPEG"), (".jpeg", "JPEG")):
                image_path = Path(directory) / f"invoice{extension}"
                Image.new("RGB", (32, 24), "white").save(image_path, format=image_format)
                with self.subTest(extension=extension):
                    with patch.object(
                        ocr_service, "_recognize_image", return_value="Recognized image text"
                    ) as recognize_image:
                        text = ocr_service.extract_text(image_path)

                    self.assertEqual(text, "Recognized image text")
                    recognize_image.assert_called_once()

    def test_detailed_pdf_result_retains_rapidocr_confidences(self) -> None:
        image_buffer = BytesIO()
        Image.new("RGB", (32, 24), "white").save(image_buffer, format="PNG")

        with tempfile.TemporaryDirectory() as directory:
            pdf_path = Path(directory) / "scanned-invoice.pdf"
            document = fitz.open()
            page = document.new_page()
            page.insert_image(page.rect, stream=image_buffer.getvalue())
            document.save(pdf_path)
            document.close()

            with patch.object(
                ocr_service,
                "_recognize_image_with_confidence",
                return_value=("Invoice number: INV-1", [0.91, 0.83]),
            ):
                result = ocr_service.extract_document(pdf_path)

        self.assertEqual(result.text, "Invoice number: INV-1")
        self.assertEqual(result.source, "rapidocr")
        self.assertEqual(result.token_confidences, [0.91, 0.83])
        self.assertAlmostEqual(result.mean_token_confidence, 0.87)

    def test_ocr_failure_is_reported_without_losing_other_page_processing(self) -> None:
        image_buffer = BytesIO()
        Image.new("RGB", (32, 24), "white").save(image_buffer, format="PNG")

        with tempfile.TemporaryDirectory() as directory:
            pdf_path = Path(directory) / "scanned-invoice.pdf"
            document = fitz.open()
            page = document.new_page()
            page.insert_image(page.rect, stream=image_buffer.getvalue())
            document.save(pdf_path)
            document.close()

            with patch.object(
                ocr_service,
                "_recognize_image_with_confidence",
                side_effect=RuntimeError("private OCR engine detail"),
            ):
                result = ocr_service.extract_document(pdf_path)

        self.assertEqual(result.text, "")
        self.assertEqual(result.source, "empty")
        self.assertIn("Page 1 could not be read by OCR.", result.warnings)
        self.assertNotIn("private OCR engine detail", str(result.warnings))

    def test_empty_corrupt_and_unsupported_documents_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            empty_pdf = Path(directory) / "empty.pdf"
            empty_pdf.write_bytes(b"")
            corrupt_image = Path(directory) / "corrupt.png"
            corrupt_image.write_bytes(b"not an image")
            unsupported = Path(directory) / "invoice.txt"
            unsupported.write_text("invoice", encoding="utf-8")

            for path in (empty_pdf, corrupt_image, unsupported):
                with self.subTest(path=path.name), self.assertRaises(OCRDocumentError):
                    ocr_service.extract_document(path)

    def test_rapidocr_score_shape_is_preserved_as_token_confidence(self) -> None:
        engine = Mock()
        engine.return_value = (
            [
                ([[0, 0], [1, 0], [1, 1], [0, 1]], "Invoice", "0.97"),
                ([[0, 1], [1, 1], [1, 2], [0, 2]], "   ", "0.5"),
            ],
            [0.01],
        )
        with patch.object(ocr_service, "_get_ocr_engine", return_value=engine):
            text, confidence = ocr_service._recognize_image_with_confidence(
                np.zeros((4, 4, 3), dtype=np.uint8)
            )

        self.assertEqual(text, "Invoice")
        self.assertEqual(confidence, [0.97])

    def test_ocr_engine_unavailable_raises_runtime_error(self) -> None:
        # Clear the lru_cache so the patch takes effect
        ocr_service._get_ocr_engine.cache_clear()
        try:
            with patch.object(ocr_service, "_is_ocr_engine_available", return_value=False):
                with self.assertRaises(RuntimeError) as ctx:
                    ocr_service._get_ocr_engine()
                self.assertIn("RapidOCR ONNX runtime is unavailable", str(ctx.exception))
        finally:
            ocr_service._get_ocr_engine.cache_clear()


if __name__ == "__main__":
    unittest.main()