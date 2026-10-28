import csv
import io
import json
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api import routes_invoices
from app.db.database import Base, get_db
from app.db.models import Invoice
from app.main import app
from app.services.n8n_service import N8NIntegrationError


WORKFLOW_RESULT = (
    {"status": "valid", "errors": [], "warnings": []},
    {"risk_level": "LOW", "findings": [], "explanation": "No obvious anomalies detected."},
    [],
    True,
)


class InvoiceAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.upload_directory = tempfile.TemporaryDirectory()
        self.uploads_path = Path(self.upload_directory.name) / "uploads"

        def override_get_db():
            with Session(self.engine) as database:
                yield database

        app.dependency_overrides[get_db] = override_get_db
        self.uploads_patch = patch.object(routes_invoices, "UPLOADS_DIR", self.uploads_path)
        self.uploads_patch.start()
        self.ocr_text = (
            "Vendor: Test Vendor\n"
            "Invoice Number: INV-TEST\n"
            "Invoice Date: 2026-10-12\n"
            "Due Date: 2026-10-22\n"
            "Currency: USD\n"
            "Subtotal: 100.00\n"
            "Discount: 0.00\n"
            "Tax: 8.00\n"
            "Total: 108.00\n"
            "Consulting service | 2 | 50.00 | 100.00"
        )
        self.ocr_patch = patch.object(
            routes_invoices,
            "extract_text",
            return_value=self.ocr_text,
        )
        self.ocr_patch.start()
        self.workflow_patch = patch.object(
            routes_invoices,
            "call_invoice_workflow",
            return_value=WORKFLOW_RESULT,
        )
        self.workflow_patch.start()
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()
        self.workflow_patch.stop()
        self.ocr_patch.stop()
        self.uploads_patch.stop()
        self.upload_directory.cleanup()
        self.engine.dispose()

    def upload_pdf(self, filename: str = "sample.pdf"):
        return self.client.post(
            "/invoices/upload",
            files={"file": (filename, b"%PDF-1.7\nplaceholder document", "application/pdf")},
        )

    def create_export_invoice(self, **fields: object) -> int:
        with Session(self.engine) as database:
            invoice = Invoice(original_filename="export.pdf", **fields)
            database.add(invoice)
            database.commit()
            database.refresh(invoice)
            return invoice.id

    def assert_no_upload_artifacts(self) -> None:
        with Session(self.engine) as database:
            invoice_ids = list(database.scalars(select(Invoice.id)).all())
        saved_files = list(self.uploads_path.glob("*")) if self.uploads_path.exists() else []
        self.assertEqual(invoice_ids, [])
        self.assertEqual(saved_files, [])

    def test_successful_upload_returns_placeholder_and_saves_file(self) -> None:
        response = self.upload_pdf()

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertIsInstance(payload["invoice_id"], int)
        self.assertEqual(payload["processing_status"], "processed")
        self.assertIn("baseline invoice-field extraction completed", payload["message"])

        retrieved = self.client.get(f"/invoices/{payload['invoice_id']}")
        self.assertEqual(retrieved.status_code, 200)
        self.assertEqual(retrieved.json()["id"], payload["invoice_id"])
        self.assertEqual(
            retrieved.json()["extracted_text"], self.ocr_text
        )
        self.assertEqual(retrieved.json()["invoice_number"], "INV-TEST")
        self.assertEqual(retrieved.json()["vendor_name"], "Test Vendor")
        self.assertEqual(retrieved.json()["total_amount"], "108.00")
        self.assertEqual(retrieved.json()["discount_amount"], "0.00")

        with Session(self.engine) as database:
            invoice = database.get(Invoice, payload["invoice_id"])
            self.assertIsNotNone(invoice)
            assert invoice is not None
            self.assertEqual(invoice.invoice_number, "INV-TEST")
            self.assertEqual(invoice.vendor_name, "Test Vendor")
            self.assertEqual(invoice.total_amount, 108)
            self.assertEqual(invoice.discount_amount, 0)
            self.assertIsNone(invoice.confidence)
            self.assertEqual(invoice.status, "uploaded")
            self.assertEqual(invoice.review_status, "pending")
            self.assertEqual(invoice.validation_warnings, [])
            saved_file = self.uploads_path / invoice.stored_filename

        self.assertTrue(saved_file.is_file())
        self.assertRegex(saved_file.name, r"^[0-9a-f]{32}\.pdf$")

    def test_unreconciled_amounts_are_persisted_and_flagged_for_review(self) -> None:
        inconsistent_text = self.ocr_text.replace("Total: 108.00", "Total: 110.00")
        with patch.object(routes_invoices, "extract_text", return_value=inconsistent_text):
            upload = self.upload_pdf("inconsistent.pdf")

        invoice_id = upload.json()["invoice_id"]
        retrieved = self.client.get(f"/invoices/{invoice_id}")

        self.assertEqual(upload.status_code, 201)
        self.assertEqual(retrieved.status_code, 200)
        self.assertEqual(retrieved.json()["review_status"], "needs_review")
        self.assertTrue(
            any(
                "Identified invoice amounts do not reconcile" in warning
                for warning in retrieved.json()["validation_warnings"]
            )
        )

    def test_unsupported_file_type_is_rejected(self) -> None:
        response = self.client.post(
            "/invoices/upload",
            files={"file": ("notes.txt", b"not an invoice", "text/plain")},
        )

        self.assertEqual(response.status_code, 415)
        self.assert_no_upload_artifacts()

    def test_empty_upload_is_rejected_without_record_or_file(self) -> None:
        response = self.client.post(
            "/invoices/upload",
            files={"file": ("empty.pdf", b"", "application/pdf")},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Uploaded file is empty.")
        self.assert_no_upload_artifacts()

    def test_mismatched_mime_type_is_rejected_without_record_or_file(self) -> None:
        response = self.client.post(
            "/invoices/upload",
            files={"file": ("invoice.pdf", b"%PDF-1.7\ncontent", "image/png")},
        )

        self.assertEqual(response.status_code, 415)
        self.assertIn("content type does not match", response.json()["detail"])
        self.assert_no_upload_artifacts()

    def test_mismatched_file_signature_is_rejected_without_record_or_file(self) -> None:
        response = self.client.post(
            "/invoices/upload",
            files={"file": ("invoice.pdf", b"not a PDF document", "application/pdf")},
        )

        self.assertEqual(response.status_code, 415)
        self.assertIn("contents do not match", response.json()["detail"])
        self.assert_no_upload_artifacts()

    def test_supported_file_types_are_accepted(self) -> None:
        uploads = [
            ("invoice.pdf", b"%PDF-1.7\ncontent", "application/pdf"),
            ("invoice.png", b"\x89PNG\r\n\x1a\ncontent", "image/png"),
            ("invoice.jpg", b"\xff\xd8\xffcontent", "image/jpeg"),
            ("invoice.jpeg", b"\xff\xd8\xffcontent", "image/jpeg"),
            (
                "invoice.csv",
                b"invoice_number,vendor_name,invoice_date,currency,subtotal,tax,total\n"
                b"CSV-1,CSV Vendor,2026-10-12,USD,100,8,108\n",
                "text/csv",
            ),
        ]

        for filename, content, content_type in uploads:
            with self.subTest(filename=filename):
                response = self.client.post(
                    "/invoices/upload",
                    files={"file": (filename, content, content_type)},
                )
                self.assertEqual(response.status_code, 201, response.text)

        with Session(self.engine) as database:
            self.assertEqual(len(list(database.scalars(select(Invoice.id)).all())), 5)
        self.assertEqual(len(list(self.uploads_path.glob("*"))), 5)

    def test_csv_upload_supports_multiple_records(self) -> None:
        content = (
            "invoice_number,vendor_name,invoice_date,currency,subtotal,tax,total\n"
            "CSV-1,CSV Vendor,2026-10-12,USD,100,8,108\n"
            "CSV-2,Another Vendor,2026-10-13,EUR,200,40,240\n"
        )
        response = self.client.post(
            "/invoices/upload",
            files={"file": ("invoices.csv", content.encode(), "text/csv")},
        )

        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["invoice_count"], 2)
        self.assertEqual(response.json()["processing_status"], "processed")
        self.assertEqual(len(response.json()["invoice_ids"]), 2)
        with Session(self.engine) as database:
            records = list(database.scalars(select(Invoice).order_by(Invoice.id)).all())
        self.assertEqual([record.invoice_number for record in records], ["CSV-1", "CSV-2"])

    def test_xlsx_upload_extracts_invoice_row(self) -> None:
        from openpyxl import Workbook

        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["invoice_number", "vendor_name", "invoice_date", "currency", "subtotal", "tax", "total"])
        sheet.append(["XLSX-1", "Workbook Vendor", "2026-10-12", "USD", 100, 8, 108])
        content = io.BytesIO()
        workbook.save(content)
        response = self.client.post(
            "/invoices/upload",
            files={
                "file": (
                    "invoice.xlsx",
                    content.getvalue(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )

        self.assertEqual(response.status_code, 201, response.text)
        invoice = self.client.get(f"/invoices/{response.json()['id']}").json()
        self.assertEqual(invoice["invoice_number"], "XLSX-1")
        self.assertEqual(invoice["source_format"], "xlsx")

    def test_impossible_calendar_date_is_not_processed(self) -> None:
        invalid_date_text = self.ocr_text.replace("2026-10-12", "2026-02-30")
        with patch.object(routes_invoices, "extract_text", return_value=invalid_date_text):
            response = self.upload_pdf("invalid-date.pdf")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["processing_status"], "failed")
        invoice = self.client.get(f"/invoices/{response.json()['id']}").json()
        self.assertEqual(invoice["invoice_date"], None)
        self.assertTrue(any("invalid or ambiguous" in str(item).lower() for item in invoice["validation_warnings"]))
        self.assertIsNone(invoice["ai_analysis"])

    def test_reupload_and_retry_reuse_existing_invoice_id(self) -> None:
        with patch.object(
            routes_invoices,
            "call_invoice_workflow",
            side_effect=[N8NIntegrationError("workflow offline"), WORKFLOW_RESULT],
        ):
            first = self.upload_pdf()
            repeated = self.upload_pdf()
        self.assertEqual(first.json()["id"], repeated.json()["id"])
        self.assertEqual(repeated.json()["invoice_count"], 1)

        with Session(self.engine) as database:
            invoice_count = len(list(database.scalars(select(Invoice.id)).all()))
        self.assertEqual(invoice_count, 1)
        self.assertEqual(repeated.json()["processing_status"], "processed")

    def test_corrupt_csv_is_rejected_without_record(self) -> None:
        response = self.client.post(
            "/invoices/upload",
            files={"file": ("broken.csv", b"\xff\xfe", "text/csv")},
        )
        self.assertEqual(response.status_code, 400)
        self.assert_no_upload_artifacts()

    def test_upload_over_size_limit_is_rejected(self) -> None:
        with patch.object(routes_invoices, "MAX_UPLOAD_SIZE_BYTES", 8):
            response = self.client.post(
                "/invoices/upload",
                files={"file": ("large.pdf", b"%PDF-1.7\n", "application/pdf")},
            )

        self.assertEqual(response.status_code, 413)
        self.assert_no_upload_artifacts()

    def test_upload_with_no_recognized_text_is_flagged_for_review(self) -> None:
        with patch.object(routes_invoices, "extract_text", return_value=""):
            response = self.upload_pdf()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["processing_status"], "failed")
        self.assertIn("no readable text was recognized", response.json()["message"])

    def test_upload_survives_ocr_failure_with_failed_status(self) -> None:
        with patch.object(routes_invoices, "extract_text", side_effect=RuntimeError("private detail")):
            response = self.upload_pdf()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["processing_status"], "failed")
        self.assertNotIn("private detail", response.json()["message"])

    def test_invoice_listing_includes_saved_upload(self) -> None:
        upload = self.upload_pdf()
        invoice_id = upload.json()["invoice_id"]

        response = self.client.get("/invoices")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([invoice["id"] for invoice in response.json()], [invoice_id])
        self.assertEqual(response.json()[0]["processing_status"], "processed")

    def test_json_export_includes_persisted_fields_and_nested_data(self) -> None:
        self.create_export_invoice(
            invoice_number="INV-JSON",
            vendor_name="Café Supply",
            invoice_date=date(2026, 10, 12),
            due_date=None,
            currency="EUR",
            subtotal=Decimal("1234.50"),
            tax_amount=None,
            discount_amount=Decimal("10.00"),
            total_amount=Decimal("1224.50"),
            line_items=[
                {"description": "Câble", "quantity": "2", "unit_price": "612.25", "total_amount": "1224.50"}
            ],
            validation_warnings=["Review café tax details"],
            processing_status="processed",
            review_status="needs_review",
        )

        response = self.client.get("/invoices/export/json")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("application/json"))
        self.assertEqual(response.headers["content-disposition"], 'attachment; filename="invoices.json"')
        payload = json.loads(response.content)
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["invoice_number"], "INV-JSON")
        self.assertEqual(payload[0]["vendor_name"], "Café Supply")
        self.assertEqual(payload[0]["invoice_date"], "2026-10-12")
        self.assertIsNone(payload[0]["due_date"])
        self.assertEqual(payload[0]["subtotal"], "1234.50")
        self.assertIsNone(payload[0]["tax_amount"])
        self.assertEqual(payload[0]["discount_amount"], "10.00")
        self.assertEqual(payload[0]["line_items"][0]["description"], "Câble")
        self.assertEqual(payload[0]["validation_warnings"], ["Review café tax details"])

    def test_csv_export_quotes_special_characters_and_serializes_nested_data(self) -> None:
        self.create_export_invoice(
            invoice_number="INV,42",
            vendor_name='Müller, "North"\nSupply',
            invoice_date=date(2026, 10, 12),
            due_date=None,
            currency=None,
            subtotal=None,
            tax_amount=Decimal("8.00"),
            discount_amount=None,
            total_amount=None,
            line_items=[
                {"description": 'Cable, "premium"\nblue', "quantity": "1", "unit_price": "8.00"}
            ],
            validation_warnings=["Check, tax", 'Review "currency"'],
        )

        response = self.client.get("/invoices/export/csv")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("text/csv"))
        self.assertEqual(response.headers["content-disposition"], 'attachment; filename="invoices.csv"')
        reader = csv.DictReader(io.StringIO(response.content.decode("utf-8")))
        self.assertEqual(
            reader.fieldnames,
            [
                "id", "original_filename", "invoice_number", "vendor_name", "invoice_date",
                "due_date", "currency", "subtotal", "tax_amount", "discount_amount",
                "total_amount", "line_items", "processing_status", "review_status",
                "validation_warnings",
            ],
        )
        rows = list(reader)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["invoice_number"], "INV,42")
        self.assertEqual(row["vendor_name"], 'Müller, "North"\nSupply')
        self.assertEqual(row["invoice_date"], "2026-10-12")
        self.assertEqual(row["due_date"], "")
        self.assertEqual(row["currency"], "")
        self.assertEqual(row["subtotal"], "")
        self.assertEqual(json.loads(row["line_items"])[0]["description"], 'Cable, "premium"\nblue')
        self.assertEqual(json.loads(row["validation_warnings"]), ["Check, tax", 'Review "currency"'])

    def test_empty_exports_return_json_list_and_csv_header(self) -> None:
        json_response = self.client.get("/invoices/export/json")
        csv_response = self.client.get("/invoices/export/csv")

        self.assertEqual(json_response.status_code, 200)
        self.assertEqual(json.loads(json_response.content), [])
        self.assertEqual(csv_response.status_code, 200)
        self.assertEqual(len(list(csv.DictReader(io.StringIO(csv_response.text)))), 0)
        self.assertIn("invoice_number", csv_response.text.splitlines()[0])

    def test_invoice_retrieval_returns_saved_invoice_or_not_found(self) -> None:
        invoice_id = self.upload_pdf().json()["invoice_id"]

        response = self.client.get(f"/invoices/{invoice_id}")
        missing = self.client.get("/invoices/99999")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], invoice_id)
        self.assertEqual(response.json()["line_items"][0]["description"], "Consulting service")
        self.assertEqual(missing.status_code, 404)

    def test_uploaded_invoice_persists_in_database(self) -> None:
        payload = self.upload_pdf().json()

        with Session(self.engine) as database:
            invoice = database.scalars(
                select(Invoice).where(Invoice.id == payload["invoice_id"])
            ).one()

        self.assertEqual(invoice.original_filename, "sample.pdf")
        self.assertTrue(invoice.stored_filename)
        self.assertEqual(invoice.extracted_text, self.ocr_text)
        self.assertEqual(invoice.invoice_number, "INV-TEST")
        self.assertEqual(invoice.validation_warnings, [])
        self.assertIsNotNone(invoice.created_at)
        self.assertIsNotNone(invoice.updated_at)

    def test_reprocessing_preserves_existing_human_values(self) -> None:
        invoice = Invoice(
            original_filename="reviewed.pdf",
            vendor_name="Human corrected vendor",
            total_amount=99,
            line_items=[{"description": "Corrected item", "quantity": "1"}],
            review_status="pending",
            validation_warnings=[],
        )
        extraction = routes_invoices.extract_invoice_data(self.ocr_text)

        routes_invoices._apply_extraction(invoice, extraction)
        with Session(self.engine) as database:
            database.add(invoice)
            database.commit()
            database.refresh(invoice)

            persisted = database.get(Invoice, invoice.id)
            assert persisted is not None
            self.assertEqual(persisted.vendor_name, "Human corrected vendor")
            self.assertEqual(persisted.total_amount, 99)
            self.assertEqual(persisted.line_items[0]["description"], "Corrected item")
            self.assertEqual(persisted.invoice_number, "INV-TEST")

    def test_patch_and_review_endpoints_update_invoice(self) -> None:
        invoice_id = self.upload_pdf().json()["invoice_id"]

        updated = self.client.patch(
            f"/invoices/{invoice_id}",
            json={"vendor_name": "Reviewed Vendor", "currency": "USD"},
        )
        reviewed = self.client.post(
            f"/invoices/{invoice_id}/review",
            json={"status": "reviewed"},
        )

        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["vendor_name"], "Reviewed Vendor")
        self.assertEqual(updated.json()["currency"], "USD")
        self.assertEqual(updated.json()["invoice_number"], "INV-TEST")
        self.assertEqual(updated.json()["line_items"][0]["description"], "Consulting service")
        self.assertEqual(reviewed.status_code, 200)
        self.assertEqual(reviewed.json()["review_status"], "reviewed")

    def test_patch_updates_invoice_fields_with_dates_and_amounts(self) -> None:
        invoice_id = self.upload_pdf().json()["invoice_id"]

        response = self.client.patch(
            f"/invoices/{invoice_id}",
            json={
                "invoice_number": "INV-100",
                "vendor_name": "Example Vendor",
                "invoice_date": "2026-10-12",
                "due_date": "2026-10-12",
                "currency": "USD",
                "subtotal": 125.50,
                "tax_amount": 10.04,
                "discount_amount": 5.00,
                "total_amount": 135.54,
                "line_items": [
                    {
                        "description": "Consulting",
                        "quantity": 2,
                        "unit_price": 62.75,
                        "tax_amount": 10.04,
                        "total_amount": 135.54,
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["invoice_number"], "INV-100")
        self.assertEqual(response.json()["invoice_date"], "2026-10-12")
        self.assertEqual(response.json()["due_date"], "2026-10-12")
        self.assertEqual(response.json()["currency"], "USD")
        self.assertEqual(response.json()["discount_amount"], "5.00")
        self.assertEqual(response.json()["line_items"][0]["description"], "Consulting")
        self.assertEqual(response.json()["line_items"][0]["quantity"], "2")

    def test_patch_updates_line_items_and_persists_them(self) -> None:
        invoice_id = self.upload_pdf().json()["invoice_id"]

        response = self.client.patch(
            f"/invoices/{invoice_id}",
            json={
                "line_items": [
                    {"description": "Service fee", "quantity": 1, "unit_price": 45.00}
                ]
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["line_items"][0]["description"], "Service fee")
        retrieved = self.client.get(f"/invoices/{invoice_id}")
        self.assertEqual(retrieved.status_code, 200)
        self.assertEqual(retrieved.json()["line_items"][0]["description"], "Service fee")
        self.assertEqual(retrieved.json()["invoice_number"], "INV-TEST")

    def test_patch_missing_invoice_returns_not_found(self) -> None:
        response = self.client.patch(
            "/invoices/99999",
            json={"vendor_name": "Missing Vendor"},
        )

        self.assertEqual(response.status_code, 404)

    def test_file_preview_streams_stored_file(self) -> None:
        upload = self.upload_pdf()
        invoice_id = upload.json()["invoice_id"]

        response = self.client.get(f"/invoices/{invoice_id}/file")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertEqual(response.content, b"%PDF-1.7\nplaceholder document")

    def test_file_preview_missing_invoice_returns_not_found(self) -> None:
        response = self.client.get("/invoices/99999/file")
        self.assertEqual(response.status_code, 404)

    def test_review_missing_invoice_returns_not_found(self) -> None:
        response = self.client.post(
            "/invoices/99999/review",
            json={"status": "reviewed"},
        )
        self.assertEqual(response.status_code, 404)

    def test_review_invalid_status_returns_bad_request(self) -> None:
        upload = self.upload_pdf()
        invoice_id = upload.json()["invoice_id"]

        response = self.client.post(
            f"/invoices/{invoice_id}/review",
            json={"status": "invalid_status"},
        )
        self.assertEqual(response.status_code, 400)

    def test_patch_supports_nested_frontend_payload(self) -> None:
        upload = self.upload_pdf()
        invoice_id = upload.json()["invoice_id"]

        response = self.client.patch(
            f"/invoices/{invoice_id}",
            json={
                "vendor": {
                    "name": "Nested Vendor Ltd",
                    "address": "456 Market St",
                    "taxId": "GSTIN987",
                },
                "discount": 15.50,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["vendor_name"], "Nested Vendor Ltd")
        self.assertEqual(response.json()["vendor_address"], "456 Market St")
        self.assertEqual(response.json()["vendor_tax_id"], "GSTIN987")
        self.assertEqual(response.json()["discount_amount"], "15.50")


if __name__ == "__main__":
    unittest.main()