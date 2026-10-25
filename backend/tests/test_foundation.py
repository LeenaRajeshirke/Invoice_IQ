import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from app.db import database as database_module
from app.db.database import Base
from app.db.models import Invoice
from app.main import app, health


class FoundationTests(unittest.TestCase):
    def test_health_endpoint_is_registered_and_returns_ok(self) -> None:
        health_route = next(
            route for route in app.routes if getattr(route, "path", None) == "/health"
        )

        self.assertEqual(health_route.endpoint, health)
        self.assertEqual(health(), {"status": "ok"})

    def test_cors_allows_frontend_on_port_5000(self) -> None:
        from fastapi.testclient import TestClient

        with TestClient(app) as client:
            response = client.options(
                "/health",
                headers={
                    "Origin": "http://localhost:5000",
                    "Access-Control-Request-Method": "GET",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get("access-control-allow-origin"), "http://localhost:5000"
        )

    def test_invoice_model_persists_in_sqlite(self) -> None:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(bind=engine)
        with Session(engine) as session:
            session.add(
                Invoice(
                    original_filename="sample.pdf",
                    invoice_number="INV-001",
                    vendor_name="Example Vendor",
                    invoice_date=date(2026, 1, 15),
                    total_amount=Decimal("42.50"),
                )
            )
            session.commit()
            saved_invoice = session.query(Invoice).one()

            self.assertEqual(saved_invoice.invoice_number, "INV-001")
            self.assertEqual(saved_invoice.total_amount, Decimal("42.50"))
            self.assertEqual(saved_invoice.processing_status, "placeholder")

        engine.dispose()

    def test_sqlite_migration_adds_discount_without_dropping_records(self) -> None:
        engine = create_engine("sqlite://")
        with engine.begin() as connection:
            connection.execute(
                text("CREATE TABLE invoices (id INTEGER PRIMARY KEY, created_at DATETIME)")
            )
            connection.execute(
                text("INSERT INTO invoices (id, created_at) VALUES (1, '2026-01-15')")
            )

        with patch.object(database_module, "engine", engine):
            database_module._migrate_existing_invoice_table()

        columns = {column["name"] for column in inspect(engine).get_columns("invoices")}
        with engine.connect() as connection:
            existing_id = connection.execute(text("SELECT id FROM invoices")).scalar_one()

        self.assertIn("discount_amount", columns)
        self.assertEqual(existing_id, 1)
        engine.dispose()


if __name__ == "__main__":
    unittest.main()