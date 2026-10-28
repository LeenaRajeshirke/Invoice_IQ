import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pymupdf as fitz

from app.services import pipeline_service
from app.services.ocr_service import OCRDocumentResult
from app.services.pipeline_service import process_invoice_document


class InvoicePipelineTests(unittest.TestCase):
    def test_digital_pdf_runs_through_extraction_and_validation(self) -> None:
        invoice_text = """Vendor: Acme Supplies
Invoice Number: AC-100
Invoice Date: 2026-10-12
Due Date: 2026-10-22
Currency: USD
Subtotal: 100.00
Tax: 8.00
Total: 108.00
Consulting service | 2 | 50.00 | 100.00
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic-invoice.pdf"
            document = fitz.open()
            document.new_page().insert_text((72, 72), invoice_text)
            document.save(path)
            document.close()

            result = process_invoice_document(path)

        self.assertEqual(result.ocr_source, "embedded_text")
        self.assertEqual(result.fields.vendor_name, "Acme Supplies")
        self.assertEqual(result.fields.invoice_number, "AC-100")
        self.assertEqual(str(result.fields.total_amount), "108.00")
        self.assertIsNone(result.ocr_mean_token_confidence)
        self.assertFalse(any(warning.code == "amount_mismatch" for warning in result.warnings))

    def test_scanned_pdf_pipeline_keeps_ocr_scores_and_surfaces_parse_uncertainty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic-scan.pdf"
            document = fitz.open()
            document.new_page()
            document.save(path)
            document.close()

            mocked_ocr = OCRDocumentResult(
                text="Invoice Date: 03/04/2026",
                source="rapidocr",
                token_confidences=[0.9, 0.8],
            )
            with patch.object(pipeline_service, "extract_document", return_value=mocked_ocr):
                result = process_invoice_document(path)

        self.assertEqual(result.ocr_source, "rapidocr")
        self.assertAlmostEqual(result.ocr_mean_token_confidence, 0.85)
        self.assertTrue(
            any(
                warning.field == "invoice_date"
                and warning.code == "ambiguous_or_invalid_field"
                for warning in result.warnings
            )
        )


if __name__ == "__main__":
    unittest.main()
