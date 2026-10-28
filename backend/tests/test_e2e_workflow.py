import io
import json
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient
import pymupdf as fitz
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api import routes_invoices
from app.db.database import Base, get_db
from app.db.models import Invoice
from app.main import app


class EndToEndWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.upload_dir = tempfile.TemporaryDirectory()
        self.uploads_path = Path(self.upload_dir.name) / "uploads"

        def override_get_db():
            with Session(self.engine) as db:
                yield db

        app.dependency_overrides[get_db] = override_get_db
        self.saved_uploads_dir = routes_invoices.UPLOADS_DIR
        routes_invoices.UPLOADS_DIR = self.uploads_path

        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()
        routes_invoices.UPLOADS_DIR = self.saved_uploads_dir
        self.upload_dir.cleanup()
        self.engine.dispose()

    def create_pdf(self, text: str) -> bytes:
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 50), text)
        buffer = doc.tobytes()
        doc.close()
        return buffer

    def test_complete_end_to_end_workflow(self) -> None:
        """Test complete workflow: upload -> process -> retrieve -> edit -> reload -> review."""
        invoice_text = (
            "From:\n"
            "Nexus Cloud Technologies\n"
            "500 Silicon Avenue, Austin TX\n"
            "Vendor Tax ID: US-TAX-778899\n"
            "To:\n"
            "Stark Enterprises\n"
            "10880 Malibu Point, CA\n"
            "Invoice Number: INV-NEXUS-9001\n"
            "Invoice Date: 2026-10-12\n"
            "Due Date: 2026-11-12\n"
            "Currency: USD\n"
            "Payment Terms: Net 30\n"
            "Subtotal: 1000.00\n"
            "Tax: 80.00\n"
            "Discount: 50.00\n"
            "Total: 1030.00\n"
            "Dedicated Cloud Cluster | 1 | 1000.00 | 1000.00\n"
        )
        pdf_bytes = self.create_pdf(invoice_text)

        # 1. Upload invoice
        upload_resp = self.client.post(
            "/invoices/upload",
            files={"file": ("nexus_invoice.pdf", pdf_bytes, "application/pdf")},
        )
        self.assertEqual(upload_resp.status_code, 201)
        upload_data = upload_resp.json()
        invoice_id = upload_data["invoice_id"]
        self.assertEqual(upload_data["processing_status"], "processed")
        self.assertIn("baseline invoice-field extraction completed", upload_data["message"])

        # 2. Retrieve extracted fields (detail)
        get_resp = self.client.get(f"/invoices/{invoice_id}")
        self.assertEqual(get_resp.status_code, 200)
        data = get_resp.json()

        self.assertEqual(data["id"], invoice_id)
        self.assertEqual(data["invoice_number"], "INV-NEXUS-9001")
        self.assertEqual(data["vendor_name"], "Nexus Cloud Technologies")
        self.assertEqual(data["vendor_address"], "500 Silicon Avenue, Austin TX")
        self.assertEqual(data["vendor_tax_id"], "US-TAX-778899")
        self.assertEqual(data["customer_name"], "Stark Enterprises")
        self.assertEqual(data["currency"], "USD")
        self.assertEqual(data["subtotal"], "1000.00")
        self.assertEqual(data["tax_amount"], "80.00")
        self.assertEqual(data["discount_amount"], "50.00")
        self.assertEqual(data["total_amount"], "1030.00")
        self.assertEqual(data["processing_status"], "processed")
        self.assertEqual(data["review_status"], "pending")
        self.assertEqual(data["original_file_url"], f"/invoices/{invoice_id}/file")

        # Line items
        self.assertEqual(len(data["line_items"]), 1)
        self.assertEqual(data["line_items"][0]["description"], "Dedicated Cloud Cluster")
        self.assertEqual(data["line_items"][0]["quantity"], "1")
        self.assertEqual(data["line_items"][0]["unit_price"], "1000.00")

        # 3. Check document file preview works
        file_resp = self.client.get(f"/invoices/{invoice_id}/file")
        self.assertEqual(file_resp.status_code, 200)
        self.assertEqual(file_resp.headers["content-type"], "application/pdf")
        self.assertEqual(file_resp.content, pdf_bytes)

        # 4. Human-in-the-loop edits: modify vendor name and add a line item
        patch_resp = self.client.patch(
            f"/invoices/{invoice_id}",
            json={
                "vendor_name": "Nexus Cloud Technologies International",
                "payment_terms": "Immediate",
                "line_items": [
                    {
                        "description": "Dedicated Cloud Cluster (Managed)",
                        "quantity": 1,
                        "unit_price": 950.00,
                        "total_amount": 950.00,
                    },
                    {
                        "description": "Premium 24/7 SLA",
                        "quantity": 1,
                        "unit_price": 80.00,
                        "total_amount": 80.00,
                    },
                ],
            },
        )
        self.assertEqual(patch_resp.status_code, 200)
        patched_data = patch_resp.json()
        self.assertEqual(patched_data["vendor_name"], "Nexus Cloud Technologies International")
        self.assertEqual(patched_data["payment_terms"], "Immediate")
        self.assertEqual(len(patched_data["line_items"]), 2)
        self.assertEqual(patched_data["line_items"][1]["description"], "Premium 24/7 SLA")

        # 5. Reload invoice and confirm edits persisted in SQLite
        reload_resp = self.client.get(f"/invoices/{invoice_id}")
        self.assertEqual(reload_resp.status_code, 200)
        reloaded = reload_resp.json()
        self.assertEqual(reloaded["vendor_name"], "Nexus Cloud Technologies International")
        self.assertEqual(reloaded["payment_terms"], "Immediate")
        self.assertEqual(len(reloaded["line_items"]), 2)
        self.assertEqual(reloaded["line_items"][0]["description"], "Dedicated Cloud Cluster (Managed)")
        self.assertEqual(reloaded["line_items"][1]["description"], "Premium 24/7 SLA")

        # 6. Change review status to 'reviewed'
        review_resp = self.client.post(
            f"/invoices/{invoice_id}/review",
            json={"status": "reviewed"},
        )
        self.assertEqual(review_resp.status_code, 200)
        self.assertEqual(review_resp.json()["review_status"], "reviewed")

        # 7. Verify status updated in database across independent query
        final_check = self.client.get(f"/invoices/{invoice_id}")
        self.assertEqual(final_check.json()["review_status"], "reviewed")

        # 8. Verify invoice appears in register listing
        list_resp = self.client.get("/invoices")
        self.assertEqual(list_resp.status_code, 200)
        ids = [inv["id"] for inv in list_resp.json()]
        self.assertIn(invoice_id, ids)

    def test_unreconciled_amounts_trigger_warnings_and_needs_review(self) -> None:
        """Test that arithmetic inconsistencies trigger warnings and flag for human review."""
        inconsistent_text = (
            "Vendor: Flawed Billing LLC\n"
            "Invoice Number: INV-ERR-01\n"
            "Subtotal: 100.00\n"
            "Tax: 10.00\n"
            "Discount: 0.00\n"
            "Total: 250.00\n"  # 100 + 10 - 0 != 250
        )
        pdf_bytes = self.create_pdf(inconsistent_text)

        upload_resp = self.client.post(
            "/invoices/upload",
            files={"file": ("inconsistent.pdf", pdf_bytes, "application/pdf")},
        )
        self.assertEqual(upload_resp.status_code, 201)
        invoice_id = upload_resp.json()["invoice_id"]

        detail = self.client.get(f"/invoices/{invoice_id}").json()
        self.assertEqual(detail["review_status"], "needs_review")
        self.assertTrue(
            any("reconcile" in w.lower() for w in detail["validation_warnings"])
        )

    def test_invoice_with_missing_fields_surfaces_warnings(self) -> None:
        """Test that partial invoices extract what is available and surface missing field warnings."""
        minimal_text = "Vendor: Minimal Co\nTotal: 50.00"
        pdf_bytes = self.create_pdf(minimal_text)

        upload_resp = self.client.post(
            "/invoices/upload",
            files={"file": ("minimal.pdf", pdf_bytes, "application/pdf")},
        )
        self.assertEqual(upload_resp.status_code, 201)
        invoice_id = upload_resp.json()["invoice_id"]

        detail = self.client.get(f"/invoices/{invoice_id}").json()
        self.assertEqual(detail["vendor_name"], "Minimal Co")
        self.assertEqual(detail["total_amount"], "50.00")
        self.assertIsNone(detail["invoice_number"])
        self.assertTrue(
            any("Invoice number was not found" in w for w in detail["validation_warnings"])
        )

    def test_invalid_file_rejected_without_artifacts(self) -> None:
        """Test rejecting invalid file formats (415) and empty files (400)."""
        # Text file
        bad_file = self.client.post(
            "/invoices/upload",
            files={"file": ("readme.txt", b"plain text", "text/plain")},
        )
        self.assertEqual(bad_file.status_code, 415)

        # Empty file
        empty_file = self.client.post(
            "/invoices/upload",
            files={"file": ("empty.pdf", b"", "application/pdf")},
        )
        self.assertEqual(empty_file.status_code, 400)
        self.assertEqual(empty_file.json()["detail"], "Uploaded file is empty.")

        # Mismatched signature
        fake_pdf = self.client.post(
            "/invoices/upload",
            files={"file": ("fake.pdf", b"not-a-real-pdf", "application/pdf")},
        )
        self.assertEqual(fake_pdf.status_code, 415)
        self.assertIn("contents do not match", fake_pdf.json()["detail"])

    def test_api_failure_error_handling(self) -> None:
        """Test 404 for missing invoice and 400 for invalid review status."""
        missing = self.client.get("/invoices/999999")
        self.assertEqual(missing.status_code, 404)

        bad_patch = self.client.patch("/invoices/999999", json={"vendor_name": "Ghost"})
        self.assertEqual(bad_patch.status_code, 404)

        bad_review = self.client.post("/invoices/999999/review", json={"status": "reviewed"})
        self.assertEqual(bad_review.status_code, 404)


if __name__ == "__main__":
    unittest.main()
