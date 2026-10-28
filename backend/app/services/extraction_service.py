import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel

from app.schemas.invoice import CURRENCY_CODES, InvoiceFields, InvoiceLineItem


class ExtractionResult(BaseModel):
    fields: InvoiceFields
    validation_warnings: list[str]


MONEY_TOKEN = r"(?:[$\u20ac\u00a3]\s*)?[-+]?\d[\d,]*(?:\.\d{1,3})?(?:\s*[A-Z]{3})?"
LINE_ITEM_PATTERN = re.compile(
    rf"^(?P<description>.+?)\s+(?P<quantity>\d+(?:\.\d+)?)\s+"
    rf"(?P<unit_price>{MONEY_TOKEN})\s+(?P<total_amount>{MONEY_TOKEN})$",
    re.IGNORECASE,
)
LINE_ITEM_TAX_PATTERN = re.compile(
    rf"^(?P<description>.+?)\s+(?P<quantity>\d+(?:\.\d+)?)\s+"
    rf"(?P<unit_price>{MONEY_TOKEN})\s+(?P<tax_rate>\d+(?:\.\d+)?)%\s+"
    rf"(?P<total_amount>{MONEY_TOKEN})$",
    re.IGNORECASE,
)
LABEL_BOUNDARY_PATTERN = re.compile(
    r"^\s*(?:vendor(?:\s+name)?|supplier(?:\s+name)?|from|to|bill\s+to|ship\s+to|"
    r"invoice\s*(?:number|no\.?|#|id)|invoice\s+date|date\s+of\s+invoice|"
    r"date\s+issued|due\s+date|payment\s+due|currency|sub[\s-]*total|"
    r"net\s+subtotal|sales\s+tax|tax(?:\s+amount)?|vat|gst|discount(?:\s+amount)?|"
    r"less\s+discount|grand\s+total|invoice\s+total|total(?:\s+amount|\s+due)?|"
    r"total\s+payable|amount\s+due|balance\s+due|order\s+number|purchase\s+order|"
    r"hrs?\s*/\s*qty|quantity|qty|service|description|rate\s*/\s*price|"
    r"unit\s+price|adjust)\s*[:#-]?\s*$",
    re.IGNORECASE,
)
SUBTOTAL_TABLE_HEADER_PATTERN = re.compile(r"^\s*(?:sub[\s-]*total|net\s+subtotal)\s*$", re.IGNORECASE)
PARTY_SECTION_PATTERN = re.compile(
    r"^\s*(?P<label>from|vendor(?:\s+name)?|supplier(?:\s+name)?|to|bill\s+to|"
    r"ship\s+to|customer(?:\s+name)?)\b\s*[:#-]?\s*(?P<value>.*?)\s*$",
    re.IGNORECASE,
)
ADDRESS_STOP_PATTERN = re.compile(
    r"^\s*(?:invoice|date\s+of\s+invoice|date\s+issued|due\s+date|payment\s+due|"
    r"currency|sub[\s-]*total|net\s+subtotal|sales\s+tax|tax|vat|gst|discount|"
    r"grand\s+total|invoice\s+total|total|amount\s+due|balance\s+due|"
    r"hrs?\s*/\s*qty|quantity|qty|description|service)\b",
    re.IGNORECASE,
)


def _next_labeled_value(lines: list[str], label_index: int) -> str | None:
    for line in lines[label_index + 1 :]:
        value = line.strip()
        if not value:
            continue
        if LABEL_BOUNDARY_PATTERN.fullmatch(value):
            return None
        return value
    return None


def _labeled_values(
    text: str, label_pattern: str, skip_label_lines: set[int] | None = None
) -> list[str]:
    label = rf"(?:{label_pattern})"
    line_patterns = (
        re.compile(rf"^\s*{label}\s*[:#]\s*(?P<value>.*?)\s*$", re.IGNORECASE),
        re.compile(rf"^\s*{label}\s+-\s+(?P<value>.*?)\s*$", re.IGNORECASE),
        re.compile(rf"^\s*{label}\s+(?P<value>\S.*?)\s*$", re.IGNORECASE),
    )
    bare_pattern = re.compile(rf"^\s*{label}\s*[:#-]?\s*$", re.IGNORECASE)
    lines = text.splitlines()
    values: list[str] = []
    for index, line in enumerate(lines):
        if skip_label_lines and index in skip_label_lines:
            continue

        if bare_pattern.fullmatch(line):
            value = _next_labeled_value(lines, index)
            if value:
                values.append(value)
            continue

        for pattern in line_patterns:
            match = pattern.match(line)
            if match:
                value = match.group("value").strip() or _next_labeled_value(lines, index)
                if value:
                    values.append(value)
                break
    return values


def _unique_value(values: list[str], field_name: str, warnings: list[str]) -> str | None:
    distinct_values = list(dict.fromkeys(value for value in values if value))
    if len(distinct_values) > 1:
        warnings.append(f"Multiple different {field_name} values were found; this field needs review.")
        return None
    return distinct_values[0] if distinct_values else None


def _parse_date(value: str) -> date | None:
    value = value.strip()
    for date_format in ("%Y-%m-%d", "%Y/%m/%d", "%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            pass

    numeric_date = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", value)
    if numeric_date:
        first, second, year = (int(part) for part in numeric_date.groups())
        if first <= 12 and second <= 12 and first != second:
            return None
        month, day = (second, first) if first > 12 else (first, second)
        try:
            return date(year, month, day)
        except ValueError:
            return None
    return None


def _extract_date(
    text: str, label_pattern: str, field_name: str, warnings: list[str]
) -> date | None:
    values = _labeled_values(text, label_pattern)
    if not values:
        warnings.append(f"{field_name} was not found in a supported format; review is required.")
        return None

    parsed_values = [_parse_date(value) for value in values]
    if any(value is None for value in parsed_values):
        warnings.append(f"{field_name} is invalid or ambiguous; review is required.")
        return None
    distinct_dates = set(parsed_values)
    if len(distinct_dates) > 1:
        warnings.append(f"Multiple different {field_name} values were found; review is required.")
        return None
    return parsed_values[0]


def _extract_currency(text: str, warnings: list[str]) -> str | None:
    labeled_values = _labeled_values(text, r"currency")
    if labeled_values:
        values = _unique_value(labeled_values, "currency", warnings)
        if values and values.upper() in CURRENCY_CODES:
            return values.upper()
        if values:
            warnings.append("Currency code is unsupported or unclear; review is required.")
            return None

    code_matches = set(re.findall(r"\b(?:AUD|CAD|CHF|CNY|EUR|GBP|INR|JPY|NZD|USD)\b", text.upper()))
    if len(code_matches) == 1:
        return code_matches.pop()
    if len(code_matches) > 1:
        warnings.append("Multiple currency codes were found; currency needs review.")
        return None
    if "\u20ac" in text:
        return "EUR"
    if "\u00a3" in text:
        return "GBP"
    if "$" in text:
        warnings.append("Dollar symbol is ambiguous without a currency code; currency needs review.")
        return None
    warnings.append("Currency was not found; review is required.")
    return None


def _parse_amount(value: str, currency: str | None = None) -> Decimal | None:
    normalized = re.sub(r"\b(?:AUD|CAD|CHF|CNY|EUR|GBP|INR|JPY|NZD|USD)\b", "", value.upper())
    normalized = re.sub(r"[$\u20ac\u00a3]\s*", "", normalized).strip()

    if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?", normalized):
        normalized = normalized.replace(",", "")
    elif re.fullmatch(r"\d+\.\d{1,2}", normalized) or re.fullmatch(r"\d+", normalized):
        pass
    elif currency == "EUR" and re.fullmatch(r"\d+,\d{1,2}", normalized):
        normalized = normalized.replace(",", ".")
    else:
        return None

    try:
        return Decimal(normalized).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def _extract_amount(
    text: str, label_pattern: str, field_name: str, currency: str | None, warnings: list[str]
) -> Decimal | None:
    skip_label_lines: set[int] = set()
    if field_name == "Subtotal":
        lines = text.splitlines()
        for index, line in enumerate(lines):
            if not SUBTOTAL_TABLE_HEADER_PATTERN.fullmatch(line):
                continue
            nearby_headers = " ".join(lines[max(0, index - 4) : index])
            if re.search(r"\b(?:hrs?\s*/\s*qty|qty|quantity)\b", nearby_headers, re.IGNORECASE) and re.search(
                r"\b(?:rate\s*/\s*price|unit\s+price)\b", nearby_headers, re.IGNORECASE
            ):
                skip_label_lines.add(index)
    values = _labeled_values(text, label_pattern, skip_label_lines)
    if not values:
        warnings.append(f"{field_name} was not found in a supported format; review is required.")
        return None

    amounts = [_parse_amount(value, currency) for value in values]
    if any(amount is None for amount in amounts):
        warnings.append(f"{field_name} is invalid or ambiguous; review is required.")
        return None
    distinct_amounts = set(amounts)
    if len(distinct_amounts) > 1:
        warnings.append(f"Multiple different {field_name} values were found; review is required.")
        return None
    return amounts[0]


def _extract_party_details(
    text: str, labels: set[str]
) -> tuple[str | None, str | None]:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = PARTY_SECTION_PATTERN.fullmatch(line)
        if not match:
            continue
        label = re.sub(r"\s+", " ", match.group("label").strip().lower())
        if label not in labels:
            continue
        inline_name = match.group("value").strip()
        section_lines = [
            candidate.strip()
            for candidate in lines[index + 1 : index + 8]
            if candidate.strip()
        ]
        name = inline_name or (section_lines.pop(0) if section_lines else None)
        if not name:
            return None, None
        address_lines: list[str] = []
        for candidate in section_lines:
            if ADDRESS_STOP_PATTERN.match(candidate) or PARTY_SECTION_PATTERN.fullmatch(candidate):
                break
            address_lines.append(candidate)
        address = "\n".join(address_lines) or None
        return name, address
    return None, None


def _parse_tax_rate(value: str) -> Decimal | None:
    normalized = value.strip().removesuffix("%").strip()
    try:
        rate = Decimal(normalized)
    except InvalidOperation:
        return None
    return rate if rate >= 0 else None


def _validate_amount_arithmetic(fields: InvoiceFields, warnings: list[str]) -> None:
    if fields.subtotal is None or fields.tax_amount is None or fields.total_amount is None:
        return

    discount = abs(fields.discount_amount or Decimal("0.00"))
    calculated_total = fields.subtotal + fields.tax_amount - discount
    if abs(calculated_total - fields.total_amount) > Decimal("0.01"):
        warnings.append(
            "Identified invoice amounts do not reconcile; review is required."
        )


def _parse_line_item(line: str, currency: str | None) -> InvoiceLineItem | None:
    tax_rate: Decimal | None = None
    if "|" in line:
        parts = [part.strip() for part in line.split("|")]
        if len(parts) == 5:
            description, quantity_text, unit_price_text, tax_rate_text, total_text = parts
            tax_rate = _parse_tax_rate(tax_rate_text)
            if tax_rate is None:
                return None
        elif len(parts) == 4:
            description, quantity_text, unit_price_text, total_text = parts
        else:
            return None
    else:
        match = LINE_ITEM_TAX_PATTERN.fullmatch(line.strip())
        if match:
            description = match.group("description").strip()
            quantity_text = match.group("quantity")
            unit_price_text = match.group("unit_price")
            total_text = match.group("total_amount")
            tax_rate = _parse_tax_rate(match.group("tax_rate"))
        else:
            match = LINE_ITEM_PATTERN.fullmatch(line.strip())
            if not match:
                return None
            description = match.group("description").strip()
            quantity_text = match.group("quantity")
            unit_price_text = match.group("unit_price")
            total_text = match.group("total_amount")

    unit_price = _parse_amount(unit_price_text, currency)
    total_amount = _parse_amount(total_text, currency)
    try:
        quantity = Decimal(quantity_text)
    except InvalidOperation:
        return None
    if (
        not description
        or quantity <= 0
        or unit_price is None
        or unit_price < 0
        or total_amount is None
        or total_amount < 0
    ):
        return None
    return InvoiceLineItem(
        description=description,
        quantity=quantity,
        unit_price=unit_price,
        tax_rate=tax_rate,
        total_amount=total_amount,
    )


def extract_invoice_data(ocr_text: str) -> ExtractionResult:
    """Extract only explicit, supported invoice patterns; this is not an ML model."""
    warnings: list[str] = []
    vendor_name, vendor_address = _extract_party_details(
        ocr_text, {"from", "vendor", "vendor name", "supplier", "supplier name"}
    )
    if vendor_name is None:
        vendor_values = _labeled_values(ocr_text, r"vendor(?:\s+name)?|supplier(?:\s+name)?|from")
        vendor_name = _unique_value(vendor_values, "vendor name", warnings)
    else:
        vendor_values = [vendor_name]
    if vendor_name is None and not vendor_values:
        warnings.append("Vendor name was not found under a supported label; review is required.")

    customer_name, customer_address = _extract_party_details(
        ocr_text, {"to", "bill to", "ship to", "customer", "customer name"}
    )
    customer_name = customer_name or _unique_value(
        _labeled_values(
            ocr_text,
            r"(?:customer(?:\s+name)?|bill\s+to|ship\s+to|to)\b",
        ),
        "customer name",
        warnings,
    )
    vendor_tax_ids = _labeled_values(
        ocr_text, r"(?:vendor\s+)?(?:tax\s*(?:id|number)|vat\s*(?:id|number)|gstin|tin)"
    )
    customer_tax_ids = _labeled_values(
        ocr_text,
        r"customer\s+(?:tax\s*(?:id|number)|vat\s*(?:id|number)|gstin|tin)",
    )
    vendor_tax_id = _unique_value(vendor_tax_ids, "vendor tax ID", warnings)
    customer_tax_id = _unique_value(customer_tax_ids, "customer tax ID", warnings)
    payment_terms = _unique_value(
        _labeled_values(ocr_text, r"payment\s+terms|terms\s+of\s+payment"),
        "payment terms",
        warnings,
    )

    invoice_numbers = _labeled_values(ocr_text, r"invoice\s*(?:number|no\.?|#)")
    invoice_number = _unique_value(invoice_numbers, "invoice number", warnings)
    if invoice_number is None and not invoice_numbers:
        warnings.append("Invoice number was not found under a supported label; review is required.")

    invoice_date = _extract_date(
        ocr_text, r"invoice\s+date|date\s+of\s+invoice|date\s+issued", "Invoice date", warnings
    )
    due_date = _extract_date(ocr_text, r"due\s+date|payment\s+due", "Due date", warnings)
    currency = _extract_currency(ocr_text, warnings)
    subtotal = _extract_amount(
        ocr_text, r"sub[\s-]*total|net\s+subtotal", "Subtotal", currency, warnings
    )
    tax_amount = _extract_amount(
        ocr_text, r"sales\s+tax|tax(?:\s+amount)?|vat|gst", "Tax amount", currency, warnings
    )
    discount_amount = _extract_amount(
        ocr_text,
        r"less\s+discount|discount(?:\s+amount)?|coupon(?:\s+discount)?",
        "Discount amount",
        currency,
        warnings,
    )
    total_amount = _extract_amount(
        ocr_text,
        r"total\s+(?:payable|due|amount)|balance\s+due|grand\s+total|invoice\s+total|"
        r"total|amount\s+due",
        "Total amount", currency, warnings,
    )

    line_items = [
        item
        for line in ocr_text.splitlines()
        if (item := _parse_line_item(line, currency)) is not None
    ]
    if not line_items:
        warnings.append("No line items matched a supported row format; review is required.")

    fields = InvoiceFields(
        vendor_name=vendor_name,
        vendor_address=vendor_address,
        vendor_tax_id=vendor_tax_id,
        customer_name=customer_name,
        customer_address=customer_address,
        customer_tax_id=customer_tax_id,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        due_date=due_date,
        currency=currency,
        payment_terms=payment_terms,
        subtotal=subtotal,
        tax_amount=tax_amount,
        discount_amount=discount_amount,
        total_amount=total_amount,
        line_items=line_items,
    )
    _validate_amount_arithmetic(fields, warnings)
    return ExtractionResult(fields=fields, validation_warnings=warnings)