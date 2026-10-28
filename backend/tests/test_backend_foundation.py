import tempfile
import unittest
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect

from app.db.database import Base
from app.db.models import Invoice
from app.main import app
from app.schemas.invoice import InvoiceCreate, InvoiceFields


class BackendFoundationTests(unittest.TestCase):
    def test_application_startup_initializes_database_and_health(self) -> None:
        with TestClient(app) as client:
            response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_invoice_schemas_accept_valid_fields_and_reject_invalid_line_items(self) -> None:
        fields = InvoiceFields(
            vendor_name="Example Vendor",
            invoice_date=date(2026, 10, 12),
            line_items=[
                {
                    "description": "Consulting",
                    "quantity": "2",
                    "unit_price": "50.00",
                    "total_amount": "100.00",
                }
            ],
        )
        self.assertEqual(fields.line_items[0].quantity, 2)

        with self.assertRaises(ValidationError):
            InvoiceFields(
                line_items=[
                    {
                        "description": "Consulting",
                        "quantity": "0",
                        "unit_price": "50.00",
                        "total_amount": "0.00",
                    }
                ]
            )

        with self.assertRaises(ValidationError):
            InvoiceCreate(original_filename="   ")

    def test_database_initialization_creates_invoice_table(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            engine = create_engine(f"sqlite:///{Path(directory) / 'test.sqlite3'}")
            Base.metadata.create_all(bind=engine)
            self.assertIn("invoices", inspect(engine).get_table_names())
            engine.dispose()

    def test_invoice_model_defaults_and_amount_persist(self) -> None:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(bind=engine)
        from sqlalchemy.orm import Session

        with Session(engine) as session:
            invoice = Invoice(original_filename="sample.pdf", total_amount="42.50")
            session.add(invoice)
            session.commit()
            session.refresh(invoice)

            self.assertEqual(invoice.total_amount, 42.50)
            self.assertEqual(invoice.processing_status, "placeholder")
            self.assertEqual(invoice.review_status, "pending")

        engine.dispose()


if __name__ == "__main__":
    unittest.main()
