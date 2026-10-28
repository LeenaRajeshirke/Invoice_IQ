import unittest
from datetime import date
from decimal import Decimal

from pydantic import ValidationError

from app.schemas.invoice import InvoiceFields
from app.services.validation_service import (
    validate_extracted_invoice,
    validate_invoice_data,
)


class InvoiceValidationTests(unittest.TestCase):
    def test_missing_required_fields_return_structured_warnings(self) -> None:
        warnings = validate_extracted_invoice(InvoiceFields())

        self.assertTrue(
            {
                "vendor_name",
                "invoice_number",
                "invoice_date",
                "total_amount",
            }.issubset({warning.field for warning in warnings})
        )
        self.assertTrue(all(warning.code and warning.severity for warning in warnings))

    def test_invalid_date_and_amount_formats_are_rejected_by_schema(self) -> None:
        with self.assertRaises(ValidationError):
            validate_invoice_data(
                {
                    "original_filename": "synthetic.pdf",
                    "invoice_date": "not-a-date",
                }
            )

        with self.assertRaises(ValidationError):
            validate_invoice_data(
                {
                    "original_filename": "synthetic.pdf",
                    "subtotal": "not-an-amount",
                }
            )

    def test_inconsistent_amounts_and_line_items_are_flagged_without_mutation(self) -> None:
        fields = InvoiceFields(
            vendor_name="Example Vendor",
            invoice_number="EX-1",
            invoice_date=date(2026, 10, 1),
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("8.00"),
            discount_amount=Decimal("5.00"),
            total_amount=Decimal("120.00"),
            line_items=[
                {
                    "description": "Service",
                    "quantity": "2",
                    "unit_price": "40.00",
                    "total_amount": "90.00",
                }
            ],
        )

        warnings = validate_extracted_invoice(fields)
        codes = {warning.code for warning in warnings}

        self.assertIn("amount_mismatch", codes)
        self.assertIn("line_total_mismatch", codes)
        self.assertIn("line_items_subtotal_mismatch", codes)
        self.assertEqual(fields.total_amount, Decimal("120.00"))

    def test_duplicate_requires_same_vendor_and_invoice_number(self) -> None:
        fields = InvoiceFields(vendor_name="Example Vendor", invoice_number="EX-1")
        existing = InvoiceFields(vendor_name=" example vendor ", invoice_number="ex-1")

        warnings = validate_extracted_invoice(fields, existing_invoices=[existing])

        self.assertTrue(any(warning.code == "possible_duplicate" for warning in warnings))

    def test_unknown_tax_does_not_assume_zero_for_total_reconciliation(self) -> None:
        fields = InvoiceFields(
            subtotal=Decimal("100"),
            discount_amount=Decimal("5"),
            total_amount=Decimal("110"),
        )

        warnings = validate_extracted_invoice(fields)

        self.assertFalse(any(warning.code == "amount_mismatch" for warning in warnings))


if __name__ == "__main__":
    unittest.main()
