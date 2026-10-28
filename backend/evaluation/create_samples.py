"""Generate legally usable, synthetic evaluation invoices and ground truth metadata.

Keeps expected answers independent and reproducible.
"""
from datetime import date
from decimal import Decimal
import io
import json
from pathlib import Path

import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont

EVAL_DIR = Path(__file__).resolve().parent
SAMPLES_DIR = EVAL_DIR / "samples"
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)


def create_digital_pdf(path: Path, lines: list[str]) -> None:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4 size
    text = "\n".join(lines)
    page.insert_text((50, 72), text, fontsize=12)
    doc.save(path)
    doc.close()


def create_image_and_scanned_pdf(
    pdf_path: Path | None,
    image_path: Path | None,
    image_format: str,
    lines: list[str],
) -> None:
    img = Image.new("RGB", (800, 1000), "white")
    draw = ImageDraw.Draw(img)
    y = 60
    # Try to load a clean font or fall back to default
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except Exception:
        font = ImageFont.load_default()

    for line in lines:
        draw.text((60, y), line, fill="black", font=font)
        y += 32

    if image_path:
        img.save(image_path, format=image_format)

    if pdf_path:
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        doc = fitz.open()
        page = doc.new_page(width=800, height=1000)
        page.insert_image(page.rect, stream=buffer.getvalue())
        doc.save(pdf_path)
        doc.close()


def generate_all() -> None:
    samples_meta = {}

    # Sample 1: Digital Standard USD
    s1_lines = [
        "From:",
        "Acme Industrial Supplies",
        "100 Industrial Parkway, Chicago IL",
        "Vendor Tax ID: US-TAX-101",
        "To:",
        "Metro Building Works",
        "200 Construction Way",
        "Invoice Number: INV-2026-101",
        "Invoice Date: 2026-10-01",
        "Due Date: 2026-10-31",
        "Currency: USD",
        "Payment Terms: Net 30",
        "Subtotal: 100.00",
        "Tax: 10.00",
        "Discount: 0.00",
        "Total: 110.00",
        "Steel Bolt Pack | 10 | 5.00 | 50.00",
        "Industrial Washer | 20 | 2.50 | 50.00",
    ]
    s1_path = SAMPLES_DIR / "inv_01_digital_standard.pdf"
    create_digital_pdf(s1_path, s1_lines)
    samples_meta["inv_01_digital_standard.pdf"] = {
        "file_type": "digital_pdf",
        "vendor_name": "Acme Industrial Supplies",
        "invoice_number": "INV-2026-101",
        "invoice_date": "2026-10-01",
        "due_date": "2026-10-31",
        "currency": "USD",
        "subtotal": "100.00",
        "tax_amount": "10.00",
        "discount_amount": "0.00",
        "total_amount": "110.00",
        "line_items_count": 2,
        "line_items": [
            {"description": "Steel Bolt Pack", "quantity": "10", "unit_price": "5.00", "total_amount": "50.00"},
            {"description": "Industrial Washer", "quantity": "20", "unit_price": "2.50", "total_amount": "50.00"},
        ],
        "arithmetic_consistent": True,
    }

    # Sample 2: Digital Discount EUR
    s2_lines = [
        "From:",
        "Bavaria Tech GmbH",
        "Maximilianstrasse 45, Munich",
        "Vendor Tax ID: DE-882991",
        "To:",
        "Euro Cloud Solutions",
        "Invoice Number: INV-DE-882",
        "Invoice Date: 2026-09-15",
        "Due Date: 2026-10-15",
        "Currency: EUR",
        "Payment Terms: Net 30",
        "Subtotal: 500.00",
        "Discount: 50.00",
        "Tax: 85.50",
        "Total: 535.50",
        "Server Maintenance | 1 | 500.00 | 500.00",
    ]
    s2_path = SAMPLES_DIR / "inv_02_digital_discount_eur.pdf"
    create_digital_pdf(s2_path, s2_lines)
    samples_meta["inv_02_digital_discount_eur.pdf"] = {
        "file_type": "digital_pdf",
        "vendor_name": "Bavaria Tech GmbH",
        "invoice_number": "INV-DE-882",
        "invoice_date": "2026-09-15",
        "due_date": "2026-10-15",
        "currency": "EUR",
        "subtotal": "500.00",
        "tax_amount": "85.50",
        "discount_amount": "50.00",
        "total_amount": "535.50",
        "line_items_count": 1,
        "line_items": [
            {"description": "Server Maintenance", "quantity": "1", "unit_price": "500.00", "total_amount": "500.00"}
        ],
        "arithmetic_consistent": True,
    }

    # Sample 3: Digital Minimal (Missing Due Date & No Line Items)
    s3_lines = [
        "From:",
        "Cornerstone Advisory",
        "Wall Street Tower 12",
        "Invoice Number: CA-4004",
        "Invoice Date: 2026-08-10",
        "Currency: USD",
        "Subtotal: 750.00",
        "Tax: 0.00",
        "Total: 750.00",
    ]
    s3_path = SAMPLES_DIR / "inv_03_digital_minimal.pdf"
    create_digital_pdf(s3_path, s3_lines)
    samples_meta["inv_03_digital_minimal.pdf"] = {
        "file_type": "digital_pdf",
        "vendor_name": "Cornerstone Advisory",
        "invoice_number": "CA-4004",
        "invoice_date": "2026-08-10",
        "due_date": None,
        "currency": "USD",
        "subtotal": "750.00",
        "tax_amount": "0.00",
        "discount_amount": None,
        "total_amount": "750.00",
        "line_items_count": 0,
        "line_items": [],
        "arithmetic_consistent": True,
    }

    # Sample 4: Digital GBP Services
    s4_lines = [
        "From:",
        "Thames Creative Studio",
        "London Bridge Walk 5",
        "Invoice Number: TCS-1102",
        "Invoice Date: 2026-07-04",
        "Due Date: 2026-07-18",
        "Currency: GBP",
        "Payment Terms: Net 14",
        "Subtotal: 800.00",
        "Tax: 160.00",
        "Total: 960.00",
        "UI Design Sprints | 2 | 400.00 | 800.00",
    ]
    s4_path = SAMPLES_DIR / "inv_04_digital_gbp.pdf"
    create_digital_pdf(s4_path, s4_lines)
    samples_meta["inv_04_digital_gbp.pdf"] = {
        "file_type": "digital_pdf",
        "vendor_name": "Thames Creative Studio",
        "invoice_number": "TCS-1102",
        "invoice_date": "2026-07-04",
        "due_date": "2026-07-18",
        "currency": "GBP",
        "subtotal": "800.00",
        "tax_amount": "160.00",
        "discount_amount": None,
        "total_amount": "960.00",
        "line_items_count": 1,
        "line_items": [
            {"description": "UI Design Sprints", "quantity": "2", "unit_price": "400.00", "total_amount": "800.00"}
        ],
        "arithmetic_consistent": True,
    }

    # Sample 5: Digital Inconsistent Math
    s5_lines = [
        "From:",
        "Global Logistics Partners",
        "Cargo Terminal 4",
        "Invoice Number: GLP-5520",
        "Invoice Date: 2026-10-05",
        "Due Date: 2026-10-25",
        "Currency: USD",
        "Subtotal: 300.00",
        "Tax: 25.00",
        "Total: 450.00",  # Inconsistent: 300 + 25 = 325 != 450
        "Freight Transport | 1 | 300.00 | 300.00",
    ]
    s5_path = SAMPLES_DIR / "inv_05_digital_inconsistent.pdf"
    create_digital_pdf(s5_path, s5_lines)
    samples_meta["inv_05_digital_inconsistent.pdf"] = {
        "file_type": "digital_pdf",
        "vendor_name": "Global Logistics Partners",
        "invoice_number": "GLP-5520",
        "invoice_date": "2026-10-05",
        "due_date": "2026-10-25",
        "currency": "USD",
        "subtotal": "300.00",
        "tax_amount": "25.00",
        "discount_amount": None,
        "total_amount": "450.00",
        "line_items_count": 1,
        "line_items": [
            {"description": "Freight Transport", "quantity": "1", "unit_price": "300.00", "total_amount": "300.00"}
        ],
        "arithmetic_consistent": False,
    }

    # Sample 6: Scanned PDF (Pure image inside PDF)
    s6_lines = [
        "From:",
        "Pacific Hardware Store",
        "Ocean View Blvd 21",
        "Invoice Number: PH-771",
        "Invoice Date: 2026-09-01",
        "Due Date: 2026-09-30",
        "Currency: USD",
        "Subtotal: 100.00",
        "Tax: 8.00",
        "Total: 108.00",
        "Copper Pipe | 4 | 25.00 | 100.00",
    ]
    s6_path = SAMPLES_DIR / "inv_06_scanned_pdf.pdf"
    create_image_and_scanned_pdf(s6_path, None, "PNG", s6_lines)
    samples_meta["inv_06_scanned_pdf.pdf"] = {
        "file_type": "scanned_pdf",
        "vendor_name": "Pacific Hardware Store",
        "invoice_number": "PH-771",
        "invoice_date": "2026-09-01",
        "due_date": "2026-09-30",
        "currency": "USD",
        "subtotal": "100.00",
        "tax_amount": "8.00",
        "discount_amount": None,
        "total_amount": "108.00",
        "line_items_count": 1,
        "line_items": [
            {"description": "Copper Pipe", "quantity": "4", "unit_price": "25.00", "total_amount": "100.00"}
        ],
        "arithmetic_consistent": True,
    }

    # Sample 7: PNG Image Invoice
    s7_lines = [
        "From:",
        "Highland Office Supplies",
        "Pine Crest Road 88",
        "Invoice Number: HOS-901",
        "Invoice Date: 2026-06-12",
        "Due Date: 2026-07-12",
        "Currency: USD",
        "Subtotal: 90.00",
        "Tax: 7.20",
        "Total: 97.20",
        "Printer Toner Cartridge | 2 | 45.00 | 90.00",
    ]
    s7_path = SAMPLES_DIR / "inv_07_image_receipt.png"
    create_image_and_scanned_pdf(None, s7_path, "PNG", s7_lines)
    samples_meta["inv_07_image_receipt.png"] = {
        "file_type": "image_png",
        "vendor_name": "Highland Office Supplies",
        "invoice_number": "HOS-901",
        "invoice_date": "2026-06-12",
        "due_date": "2026-07-12",
        "currency": "USD",
        "subtotal": "90.00",
        "tax_amount": "7.20",
        "discount_amount": None,
        "total_amount": "97.20",
        "line_items_count": 1,
        "line_items": [
            {"description": "Printer Toner Cartridge", "quantity": "2", "unit_price": "45.00", "total_amount": "90.00"}
        ],
        "arithmetic_consistent": True,
    }

    # Sample 8: JPEG Image Invoice
    s8_lines = [
        "From:",
        "Lyon Catering Services",
        "Rue de la Paix 14",
        "Invoice Number: LCS-334",
        "Invoice Date: 2026-05-20",
        "Due Date: 2026-06-20",
        "Currency: EUR",
        "Subtotal: 150.00",
        "Tax: 15.00",
        "Total: 165.00",
        "Event Breakfast Platters | 5 | 30.00 | 150.00",
    ]
    s8_path = SAMPLES_DIR / "inv_08_image_receipt.jpg"
    create_image_and_scanned_pdf(None, s8_path, "JPEG", s8_lines)
    samples_meta["inv_08_image_receipt.jpg"] = {
        "file_type": "image_jpeg",
        "vendor_name": "Lyon Catering Services",
        "invoice_number": "LCS-334",
        "invoice_date": "2026-05-20",
        "due_date": "2026-06-20",
        "currency": "EUR",
        "subtotal": "150.00",
        "tax_amount": "15.00",
        "discount_amount": None,
        "total_amount": "165.00",
        "line_items_count": 1,
        "line_items": [
            {"description": "Event Breakfast Platters", "quantity": "5", "unit_price": "30.00", "total_amount": "150.00"}
        ],
        "arithmetic_consistent": True,
    }

    # Save Ground Truth
    gt_path = EVAL_DIR / "ground_truth.json"
    with open(gt_path, "w", encoding="utf-8") as f:
        json.dump(samples_meta, f, indent=2)

    print(f"Generated {len(samples_meta)} evaluation samples in {SAMPLES_DIR}")
    print(f"Saved ground truth metadata to {gt_path}")


if __name__ == "__main__":
    generate_all()
