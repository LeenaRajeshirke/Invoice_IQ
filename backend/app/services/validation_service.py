from collections.abc import Iterable, Sequence
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.invoice import InvoiceCreate, InvoiceFields


class ValidationWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str | None
    code: str
    severity: Literal["info", "warning", "error"]
    message: str


def validate_invoice_data(data: dict[str, object]) -> InvoiceCreate:
    """Validate invoice field formats and constraints without changing values."""
    return InvoiceCreate.model_validate(data)


def _warning_from_extraction(message: str) -> ValidationWarning:
    field_by_prefix = (
        ("Vendor name", "vendor_name"),
        ("Customer name", "customer_name"),
        ("Invoice number", "invoice_number"),
        ("Invoice date", "invoice_date"),
        ("Due date", "due_date"),
        ("Currency", "currency"),
        ("Subtotal", "subtotal"),
        ("Tax amount", "tax_amount"),
        ("Discount amount", "discount_amount"),
        ("Total amount", "total_amount"),
        ("No line items", "line_items"),
    )
    field = next((name for prefix, name in field_by_prefix if message.startswith(prefix)), None)
    lowered = message.lower()
    if "not found" in lowered or "no line items" in lowered:
        code = "missing_field"
    elif "reconcile" in lowered:
        code = "amount_mismatch"
        field = "total_amount"
    else:
        code = "ambiguous_or_invalid_field"
    severity: Literal["info", "warning", "error"] = (
        "info" if code == "missing_field" and field == "line_items" else "warning"
    )
    return ValidationWarning(
        field=field,
        code=code,
        severity=severity,
        message=message,
    )


def validate_extracted_invoice(
    fields: InvoiceFields,
    extraction_warnings: Sequence[str] = (),
    existing_invoices: Iterable[InvoiceFields | dict[str, object]] = (),
) -> list[ValidationWarning]:
    """Return non-mutating business and extraction warnings for parsed fields."""
    warnings = [_warning_from_extraction(message) for message in extraction_warnings]
    warned_codes = {(warning.field, warning.code) for warning in warnings}

    def add(
        field: str | None,
        code: str,
        severity: Literal["info", "warning", "error"],
        message: str,
    ) -> None:
        if (field, code) in warned_codes:
            return
        warnings.append(
            ValidationWarning(field=field, code=code, severity=severity, message=message)
        )
        warned_codes.add((field, code))

    for field in ("vendor_name", "invoice_number", "invoice_date", "total_amount"):
        if getattr(fields, field) is None and not any(
            warning.field == field for warning in warnings
        ):
            add(
                field,
                "required_field_missing",
                "warning",
                f"Required invoice field '{field}' was not extracted.",
            )

    if (
        fields.invoice_date is not None
        and fields.due_date is not None
        and fields.due_date < fields.invoice_date
    ):
        add(
            "due_date",
            "date_order_invalid",
            "warning",
            "Due date is earlier than the invoice date.",
        )

    amount_fields = ("subtotal", "tax_amount", "discount_amount", "total_amount")
    for field in amount_fields:
        value = getattr(fields, field)
        if value is not None and value < Decimal("0"):
            add(field, "negative_amount", "error", f"{field} cannot be negative.")

    for index, item in enumerate(fields.line_items):
        if item.quantity is not None and item.quantity <= 0:
            add(
                f"line_items[{index}].quantity",
                "invalid_quantity",
                "error",
                "Line-item quantity must be greater than zero.",
            )
        if item.unit_price is not None and item.unit_price < 0:
            add(
                f"line_items[{index}].unit_price",
                "negative_amount",
                "error",
                "Line-item unit price cannot be negative.",
            )
        if item.total_amount is not None and item.total_amount < 0:
            add(
                f"line_items[{index}].total_amount",
                "negative_amount",
                "error",
                "Line-item total cannot be negative.",
            )
        if item.tax_rate is not None and item.tax_rate < 0:
            add(
                f"line_items[{index}].tax_rate",
                "invalid_tax_rate",
                "error",
                "Line-item tax rate cannot be negative.",
            )
        elif item.tax_rate is not None and item.tax_rate > Decimal("100"):
            add(
                f"line_items[{index}].tax_rate",
                "unusual_tax_rate",
                "warning",
                "Line-item tax rate exceeds 100%; verify the extracted value.",
            )
        if (
            item.quantity is not None
            and item.unit_price is not None
            and item.total_amount is not None
        ):
            calculated = item.quantity * item.unit_price
            if item.tax_amount is not None:
                calculated += item.tax_amount
            elif item.tax_rate is not None:
                calculated *= Decimal("1") + item.tax_rate / Decimal("100")
            if abs(calculated - item.total_amount) > Decimal("0.01"):
                add(
                    f"line_items[{index}].total_amount",
                    "line_total_mismatch",
                    "warning",
                    "Line-item total does not match quantity, unit price, and tax.",
                )

    if fields.subtotal is not None and fields.line_items:
        if all(
            item.quantity is not None and item.unit_price is not None
            for item in fields.line_items
        ):
            line_subtotal = sum(
                item.quantity * item.unit_price
                for item in fields.line_items
                if item.quantity is not None and item.unit_price is not None
            )
        elif all(item.total_amount is not None for item in fields.line_items):
            line_subtotal = sum(
                item.total_amount
                for item in fields.line_items
                if item.total_amount is not None
            )
        else:
            line_subtotal = fields.subtotal
        if abs(line_subtotal - fields.subtotal) > Decimal("0.01"):
            add(
                "subtotal",
                "line_items_subtotal_mismatch",
                "warning",
                "The sum of line-item totals does not match the subtotal.",
            )

    if (
        fields.subtotal is not None
        and fields.tax_amount is not None
        and fields.total_amount is not None
    ):
        calculated_total = (
            fields.subtotal
            + fields.tax_amount
            - abs(fields.discount_amount or Decimal("0"))
        )
        if abs(calculated_total - fields.total_amount) > Decimal("0.01"):
            add(
                "total_amount",
                "amount_mismatch",
                "warning",
                "Subtotal, tax, discount, and grand total do not reconcile.",
            )

    if fields.vendor_name and fields.invoice_number:
        normalized_vendor = fields.vendor_name.casefold().strip()
        normalized_number = fields.invoice_number.casefold().strip()
        for existing in existing_invoices:
            if isinstance(existing, InvoiceFields):
                existing_vendor = existing.vendor_name
                existing_number = existing.invoice_number
            else:
                existing_vendor = existing.get("vendor_name")
                existing_number = existing.get("invoice_number")
            if (
                isinstance(existing_vendor, str)
                and isinstance(existing_number, str)
                and existing_vendor.casefold().strip() == normalized_vendor
                and existing_number.casefold().strip() == normalized_number
            ):
                add(
                    "invoice_number",
                    "possible_duplicate",
                    "warning",
                    "An invoice with the same vendor and invoice number already exists.",
                )
                break

    return warnings
