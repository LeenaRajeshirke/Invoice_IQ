import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pymupdf as fitz
from PIL import Image

from app.services import ocr_service


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


if __name__ == "__main__":
    unittest.main()