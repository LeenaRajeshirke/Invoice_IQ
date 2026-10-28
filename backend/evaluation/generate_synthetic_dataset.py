"""Generate a reproducible synthetic invoice dataset for InvoiceIQ testing."""

from datetime import date, timedelta
from decimal import Decimal
import io
import json
from pathlib import Path

import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont


DATASET_DIR = Path(__file__).resolve().parent / "synthetic_dataset"

VENDORS = [
    ("Aster Office Goods", "USD"),
    ("Blue Finch Software", "EUR"),
    ("Cedar Ridge Freight", "GBP"),
    ("Delta Workshop Supply", "CAD"),
    ("Evergreen Design House", "AUD"),
    ("Foxglove Catering", "EUR"),
    ("Granite Peak Services", "USD"),
    ("Harborlight Components", "INR"),
]

CUSTOMERS = [
    "Northstar Community Works",
    "Orchard Lane Studio",
    "Pinecone Research Group",
    "Quartz River Trading",
]

PRODUCTS = [
    "Archive Storage Box",
    "Consulting Service",
    "Delivery Charge",
    "Equipment Rental",
    "Filter Cartridge",
    "Graphic Design Package",
    "Network Adapter",
    "Workshop Materials",
]

TAX_RATES = [Decimal("0"), Decimal("5"), Decimal("8"), Decimal("10"), Decimal("20")]


def _money(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01')):.2f}"


def _render_pdf(path: Path, lines: list[str]) -> None:
    document = fitz.open()
    page = document.new_page(width=595, height=842)
    page.insert_text((48, 56), "\n".join(lines), fontsize=11)
    document.save(path)
    document.close()


def _render_image(path: Path, lines: list[str]) -> None:
    image = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", 28)
    except OSError:
        font = ImageFont.load_default()

    y = 80
    for line in lines:
        draw.text((80, y), line, fill="black", font=font)
        y += 54
    image.save(path)


def _invoice(index: int) -> tuple[list[str], dict[str, object]]:
    vendor, currency = VENDORS[index % len(VENDORS)]
    customer = CUSTOMERS[index % len(CUSTOMERS)]
    invoice_date = date(2026, 1, 5) + timedelta(days=index * 7)
    due_date = invoice_date + timedelta(days=14 + (index % 3) * 7)
    item_count = 1 + index % 3
    line_items: list[dict[str, str]] = []
    lines = [
        "From:",
        vendor,
        f"{100 + index} Example Road",
        "To:",
        customer,
        f"Invoice Number: IQ-SYN-{index + 1:04d}",
        f"Invoice Date: {invoice_date.isoformat()}",
        f"Due Date: {due_date.isoformat()}",
        f"Currency: {currency}",
        "Payment Terms: Net 30",
    ]

    subtotal = Decimal("0.00")
    for item_index in range(item_count):
        quantity = Decimal(1 + ((index + item_index) % 5))
        unit_price = Decimal(12 + index * 3 + item_index * 7) + Decimal("0.50")
        line_total = (quantity * unit_price).quantize(Decimal("0.01"))
        subtotal += line_total
        description = PRODUCTS[(index + item_index) % len(PRODUCTS)]
        lines.append(
            f"{description} | {quantity:g} | {_money(unit_price)} | {_money(line_total)}"
        )
        line_items.append(
            {
                "description": description,
                "quantity": str(quantity),
                "unit_price": _money(unit_price),
                "total_amount": _money(line_total),
            }
        )

    tax_rate = TAX_RATES[index % len(TAX_RATES)]
    tax_amount = (subtotal * tax_rate / Decimal("100")).quantize(Decimal("0.01"))
    discount = (
        (subtotal * Decimal("0.05")).quantize(Decimal("0.01"))
        if index % 4 == 1
        else Decimal("0.00")
    )
    total = subtotal + tax_amount - discount
    arithmetic_consistent = True

    # Include deliberate reconciliation failures for validation-warning testing.
    if index in (8, 18):
        total += Decimal("10.00")
        arithmetic_consistent = False

    lines.extend(
        [
            f"Subtotal: {_money(subtotal)}",
            f"Tax: {_money(tax_amount)}",
        ]
    )
    if discount:
        lines.append(f"Discount: {_money(discount)}")
    lines.append(f"Total: {_money(total)}")

    metadata: dict[str, object] = {
        "file_type": "digital_pdf",
        "vendor_name": vendor,
        "invoice_number": f"IQ-SYN-{index + 1:04d}",
        "invoice_date": invoice_date.isoformat(),
        "due_date": due_date.isoformat(),
        "currency": currency,
        "subtotal": _money(subtotal),
        "tax_amount": _money(tax_amount),
        "discount_amount": _money(discount) if discount else None,
        "total_amount": _money(total),
        "line_items_count": len(line_items),
        "line_items": line_items,
        "arithmetic_consistent": arithmetic_consistent,
    }
    return lines, metadata


def generate_dataset() -> None:
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    ground_truth: dict[str, dict[str, object]] = {}
    invoice_lines: dict[str, list[str]] = {}

    for index in range(20):
        filename = f"synthetic_{index + 1:03d}.pdf"
        lines, metadata = _invoice(index)
        _render_pdf(DATASET_DIR / filename, lines)
        ground_truth[filename] = metadata
        invoice_lines[filename] = lines

    # Include raster formats for end-to-end OCR smoke testing.
    for index, suffix, file_type in (
        (20, ".png", "image_png"),
        (21, ".jpg", "image_jpeg"),
    ):
        filename = f"synthetic_{index + 1:03d}{suffix}"
        lines, metadata = _invoice(index)
        _render_image(DATASET_DIR / filename, lines)
        metadata["file_type"] = file_type
        ground_truth[filename] = metadata
        invoice_lines[filename] = lines

    scanned_filename = "synthetic_023_scanned.pdf"
    scanned_lines, scanned_metadata = _invoice(22)
    image = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", 28)
    except OSError:
        font = ImageFont.load_default()
    y = 80
    for line in scanned_lines:
        draw.text((80, y), line, fill="black", font=font)
        y += 54
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    document = fitz.open()
    page = document.new_page(width=595, height=842)
    page.insert_image(page.rect, stream=buffer.getvalue())
    document.save(DATASET_DIR / scanned_filename)
    document.close()
    scanned_metadata["file_type"] = "scanned_pdf"
    ground_truth[scanned_filename] = scanned_metadata
    invoice_lines[scanned_filename] = scanned_lines

    (DATASET_DIR / "ground_truth.json").write_text(
        json.dumps(ground_truth, indent=2), encoding="utf-8"
    )
    (DATASET_DIR / "source_text.json").write_text(
        json.dumps(invoice_lines, indent=2), encoding="utf-8"
    )
    print(f"Generated {len(ground_truth)} invoices in {DATASET_DIR}")
    print("Dataset: 20 digital PDFs, 2 raster images, 1 scanned PDF")
    print("Synthetic reconciliation errors: synthetic_009.pdf and synthetic_019.pdf")


if __name__ == "__main__":
    generate_dataset()
