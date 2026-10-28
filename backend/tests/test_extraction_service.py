import unittest
from datetime import date
from decimal import Decimal

from app.services.extraction_service import extract_invoice_data


REALISTIC_PDF_OCR_TEXT = """Invoice
Payment is due within 30 days from date of invoice. Late payment is subject to fees of 5% per month.
Thanks for choosing DEMO - Sliced Invoices | admin@slicedinvoices.com
Page 1/1
From:
DEMO - Sliced Invoices
Suite 5A-1204
123 Somewhere Street
Your City AZ 12345
admin@slicedinvoices.com
Invoice Number
INV-3337
Order Number
12345
Invoice Date
January 25, 2016
Due Date
January 31, 2016
Total Due
$93.50
To:
Test Business
123 Somewhere St
Melbourne, VIC 3000
test@test.com
Hrs/Qty
Service
Rate/Price
Adjust
Sub Total
1.00
Web Design
This is a sample description...
$85.00
0.00%
$85.00
Sub Total
$85.00
Tax
$8.50
Total
$93.50
ANZ Bank
ACC # 1234 1234
BSB # 4321 432
Paid
"""


class InvoiceExtractionTests(unittest.TestCase):
    def test_extracts_party_addresses_tax_ids_terms_and_line_tax_rate(self) -> None:
        text = """From:
Acme Supplies
12 Main Street
Vendor Tax ID: VEND-123
To: Northwind Ltd
8 Market Road
Customer Tax ID: CUST-456
Invoice Number: AC-204
Invoice Date: 2026-10-12
Due Date: 2026-10-30
Payment Terms: Net 18
Currency: USD
Subtotal: 20.00
Tax: 1.00
Total: 21.00
Widget | 2 | 10.00 | 5% | 21.00
"""

        result = extract_invoice_data(text)

        self.assertEqual(result.fields.vendor_name, "Acme Supplies")
        self.assertEqual(result.fields.vendor_address, "12 Main Street")
        self.assertEqual(result.fields.vendor_tax_id, "VEND-123")
        self.assertEqual(result.fields.customer_name, "Northwind Ltd")
        self.assertEqual(result.fields.customer_address, "8 Market Road")
        self.assertEqual(result.fields.customer_tax_id, "CUST-456")
        self.assertEqual(result.fields.payment_terms, "Net 18")
        self.assertEqual(result.fields.line_items[0].tax_rate, Decimal("5"))

    def test_synthetic_fixture_field_exact_match(self) -> None:
        fixtures = [
            (
                """Vendor: Northwind Office Supply
Invoice Number: INV-2026-041
Invoice Date: October 12, 2026
Due Date: October 26, 2026
Currency: USD
Subtotal: 1,234.50
Tax: 96.76
Total: 1,331.26
""",
                {
                    "vendor_name": "Northwind Office Supply",
                    "invoice_number": "INV-2026-041",
                    "invoice_date": date(2026, 10, 12),
                    "due_date": date(2026, 10, 26),
                    "currency": "USD",
                    "subtotal": Decimal("1234.50"),
                    "tax_amount": Decimal("96.76"),
                    "total_amount": Decimal("1331.26"),
                },
            ),
            (
                """Vendor: Example Services
Invoice No: ES-9
Date of Invoice: 2026-02-03
Payment Due: 2026-02-20
Currency: EUR
Net Subtotal: 100.00
Sales Tax: 20.00
Less Discount: 5.00
Grand Total: 115.00
""",
                {
                    "vendor_name": "Example Services",
                    "invoice_number": "ES-9",
                    "invoice_date": date(2026, 2, 3),
                    "due_date": date(2026, 2, 20),
                    "currency": "EUR",
                    "subtotal": Decimal("100.00"),
                    "tax_amount": Decimal("20.00"),
                    "total_amount": Decimal("115.00"),
                },
            ),
        ]
        matches = 0
        total = 0
        for text, expected in fixtures:
            actual = extract_invoice_data(text).fields
            for field, expected_value in expected.items():
                total += 1
                matches += getattr(actual, field) == expected_value

        self.assertEqual((matches, total), (16, 16))

    def test_extracts_explicit_invoice_fields_and_line_items(self) -> None:
        text = """Vendor: Northwind Office Supply
Invoice Number: INV-2026-041
Invoice Date: October 12, 2026
Due Date: October 26, 2026
Currency: USD
Subtotal: $1,234.50
Discount: $25.00
Tax: $96.76
Total: $1,306.26
Ergonomic chair | 2 | $500.00 | $1,000.00
Delivery service 1 $234.50 $234.50
"""

        result = extract_invoice_data(text)

        self.assertEqual(result.fields.vendor_name, "Northwind Office Supply")
        self.assertEqual(result.fields.invoice_number, "INV-2026-041")
        self.assertEqual(result.fields.invoice_date, date(2026, 10, 12))
        self.assertEqual(result.fields.due_date, date(2026, 10, 26))
        self.assertEqual(result.fields.currency, "USD")
        self.assertEqual(result.fields.subtotal, Decimal("1234.50"))
        self.assertEqual(result.fields.discount_amount, Decimal("25.00"))
        self.assertEqual(result.fields.tax_amount, Decimal("96.76"))
        self.assertEqual(result.fields.total_amount, Decimal("1306.26"))
        self.assertEqual(len(result.fields.line_items), 2)
        self.assertEqual(result.fields.line_items[0].description, "Ergonomic chair")
        self.assertEqual(result.fields.line_items[0].quantity, Decimal("2"))
        self.assertEqual(result.fields.line_items[0].unit_price, Decimal("500.00"))
        self.assertEqual(result.fields.line_items[0].total_amount, Decimal("1000.00"))
        self.assertEqual(result.validation_warnings, [])

    def test_extracts_fields_from_realistic_multiline_pdf_ocr_text(self) -> None:
        result = extract_invoice_data(REALISTIC_PDF_OCR_TEXT)

        self.assertEqual(result.fields.vendor_name, "DEMO - Sliced Invoices")
        self.assertEqual(result.fields.invoice_number, "INV-3337")
        self.assertEqual(result.fields.invoice_date, date(2016, 1, 25))
        self.assertEqual(result.fields.due_date, date(2016, 1, 31))
        self.assertEqual(result.fields.subtotal, Decimal("85.00"))
        self.assertEqual(result.fields.tax_amount, Decimal("8.50"))
        self.assertEqual(result.fields.total_amount, Decimal("93.50"))
        self.assertIsNone(result.fields.discount_amount)
        self.assertIsNone(result.fields.currency)
        self.assertTrue(any("Dollar symbol is ambiguous" in warning for warning in result.validation_warnings))
        self.assertFalse(any("Subtotal is invalid" in warning for warning in result.validation_warnings))
        self.assertFalse(any("Total amount is invalid" in warning for warning in result.validation_warnings))

    def test_common_amount_label_variants_do_not_cross_assign_values(self) -> None:
        text = """Currency: USD
Invoice No INV-77
Date of Invoice: 2026-10-12
Payment Due
2026-10-22
Net Subtotal: 100.00
Sales Tax
8.00
Less Discount: 5.00
Balance Due
103.00
"""

        result = extract_invoice_data(text)

        self.assertEqual(result.fields.invoice_number, "INV-77")
        self.assertEqual(result.fields.invoice_date, date(2026, 10, 12))
        self.assertEqual(result.fields.due_date, date(2026, 10, 22))
        self.assertEqual(result.fields.subtotal, Decimal("100.00"))
        self.assertEqual(result.fields.tax_amount, Decimal("8.00"))
        self.assertEqual(result.fields.discount_amount, Decimal("5.00"))
        self.assertEqual(result.fields.total_amount, Decimal("103.00"))

    def test_unreconciled_amounts_are_flagged(self) -> None:
        text = "Currency: USD\nSubtotal: 100.00\nTax: 8.00\nDiscount: 5.00\nTotal: 110.00"

        result = extract_invoice_data(text)

        self.assertTrue(
            any("Identified invoice amounts do not reconcile" in warning for warning in result.validation_warnings)
        )

    def test_missing_fields_remain_empty_and_are_flagged(self) -> None:
        result = extract_invoice_data("Thank you for your business.")

        self.assertIsNone(result.fields.vendor_name)
        self.assertIsNone(result.fields.invoice_number)
        self.assertIsNone(result.fields.invoice_date)
        self.assertIsNone(result.fields.discount_amount)
        self.assertIsNone(result.fields.total_amount)
        self.assertEqual(result.fields.line_items, [])
        self.assertTrue(result.validation_warnings)

    def test_percentage_discount_is_not_guessed_as_an_amount(self) -> None:
        result = extract_invoice_data("Currency: USD\nDiscount: 10%")

        self.assertIsNone(result.fields.discount_amount)
        self.assertTrue(
            any("Discount amount is invalid or ambiguous" in warning for warning in result.validation_warnings)
        )

    def test_ambiguous_numeric_date_is_not_guessed(self) -> None:
        result = extract_invoice_data("Invoice Date: 03/04/2026")

        self.assertIsNone(result.fields.invoice_date)
        self.assertTrue(any("Invoice date is invalid or ambiguous" in warning for warning in result.validation_warnings))

    def test_ambiguous_amount_is_not_guessed(self) -> None:
        result = extract_invoice_data("Currency: USD\nTotal: 1.234,56")

        self.assertIsNone(result.fields.total_amount)
        self.assertTrue(any("Total amount is invalid or ambiguous" in warning for warning in result.validation_warnings))

    def test_dollar_symbol_without_currency_code_is_flagged(self) -> None:
        result = extract_invoice_data("Total: $125.00")

        self.assertEqual(result.fields.total_amount, Decimal("125.00"))
        self.assertIsNone(result.fields.currency)
        self.assertTrue(any("Dollar symbol is ambiguous" in warning for warning in result.validation_warnings))


if __name__ == "__main__":
    unittest.main()