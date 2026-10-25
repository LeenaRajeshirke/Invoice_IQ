from collections.abc import Sequence
import csv
import io
import json
from typing import Literal

from app.schemas.invoice import InvoiceRead

CSV_FIELDS = (
    "id",
    "original_filename",
    "invoice_number",
    "vendor_name",
    "invoice_date",
    "due_date",
    "currency",
    "subtotal",
    "tax_amount",
    "discount_amount",
    "total_amount",
    "line_items",
    "processing_status",
    "review_status",
    "validation_warnings",
)


def export_invoices(
    invoices: Sequence[InvoiceRead], output_format: Literal["csv", "json"]
) -> bytes:
    """Serialize invoice response models to JSON or CSV without losing nulls."""
    if output_format == "json":
        data = [invoice.model_dump(mode="json") for invoice in invoices]
        return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")

    if output_format == "csv":
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=CSV_FIELDS, lineterminator="\r\n")
        writer.writeheader()
        for invoice in invoices:
            writer.writerow(
                {
                    "id": invoice.id,
                    "original_filename": invoice.original_filename,
                    "invoice_number": invoice.invoice_number or "",
                    "vendor_name": invoice.vendor_name or "",
                    "invoice_date": invoice.invoice_date.isoformat() if invoice.invoice_date else "",
                    "due_date": invoice.due_date.isoformat() if invoice.due_date else "",
                    "currency": invoice.currency or "",
                    "subtotal": str(invoice.subtotal) if invoice.subtotal is not None else "",
                    "tax_amount": str(invoice.tax_amount) if invoice.tax_amount is not None else "",
                    "discount_amount": (
                        str(invoice.discount_amount) if invoice.discount_amount is not None else ""
                    ),
                    "total_amount": str(invoice.total_amount) if invoice.total_amount is not None else "",
                    "line_items": json.dumps(
                        [item.model_dump(mode="json") for item in invoice.line_items],
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    "processing_status": invoice.processing_status,
                    "review_status": invoice.review_status,
                    "validation_warnings": json.dumps(
                        invoice.validation_warnings,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                }
            )
        return output.getvalue().encode("utf-8")

    raise ValueError(f"Unsupported invoice export format: {output_format}")