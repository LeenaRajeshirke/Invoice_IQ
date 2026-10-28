from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.database import get_db
from app.db.models import Invoice
from app.schemas.invoice import (
    InvoiceLineItem,
    InvoiceRead,
    InvoiceReviewRequest,
    InvoiceUpdate,
    InvoiceUploadResponse,
)
from app.services import export_service
from app.services.extraction_service import (
    ExtractionResult,
    extract_invoice_data as extraction_extract_invoice_data,
)
from app.services.ocr_service import extract_text as ocr_extract_text

# Module-level exports for configuration and monkey-patching in tests
UPLOADS_DIR = settings.uploads_dir
MAX_UPLOAD_SIZE_BYTES = settings.max_upload_size_bytes
extract_text = ocr_extract_text
extract_invoice_data = extraction_extract_invoice_data

SUPPORTED_FORMATS: dict[str, tuple[str, bytes]] = {
    ".pdf": ("application/pdf", b"%PDF-"),
    ".png": ("image/png", b"\x89PNG\r\n\x1a\n"),
    ".jpg": ("image/jpeg", b"\xff\xd8\xff"),
    ".jpeg": ("image/jpeg", b"\xff\xd8\xff"),
}

VALID_REVIEW_STATUSES = {"reviewed", "needs_review", "rejected", "pending"}

router = APIRouter(prefix="/invoices", tags=["invoices"])


def _apply_extraction(invoice: Invoice, extraction: ExtractionResult) -> None:
    """Transfer extracted fields to an invoice record while preserving any non-null existing values."""
    fields = extraction.fields

    if invoice.vendor_name is None and fields.vendor_name is not None:
        invoice.vendor_name = fields.vendor_name
    if invoice.vendor_address is None and fields.vendor_address is not None:
        invoice.vendor_address = fields.vendor_address
    if invoice.vendor_tax_id is None and fields.vendor_tax_id is not None:
        invoice.vendor_tax_id = fields.vendor_tax_id

    if invoice.customer_name is None and fields.customer_name is not None:
        invoice.customer_name = fields.customer_name
    if invoice.customer_address is None and fields.customer_address is not None:
        invoice.customer_address = fields.customer_address
    if invoice.customer_tax_id is None and fields.customer_tax_id is not None:
        invoice.customer_tax_id = fields.customer_tax_id

    if invoice.invoice_number is None and fields.invoice_number is not None:
        invoice.invoice_number = fields.invoice_number
    if invoice.invoice_date is None and fields.invoice_date is not None:
        invoice.invoice_date = fields.invoice_date
    if invoice.due_date is None and fields.due_date is not None:
        invoice.due_date = fields.due_date
    if invoice.currency is None and fields.currency is not None:
        invoice.currency = fields.currency
    if invoice.payment_terms is None and fields.payment_terms is not None:
        invoice.payment_terms = fields.payment_terms

    if invoice.subtotal is None and fields.subtotal is not None:
        invoice.subtotal = fields.subtotal
    if invoice.tax_amount is None and fields.tax_amount is not None:
        invoice.tax_amount = fields.tax_amount
    if invoice.discount_amount is None and fields.discount_amount is not None:
        invoice.discount_amount = fields.discount_amount
    if invoice.total_amount is None and fields.total_amount is not None:
        invoice.total_amount = fields.total_amount

    if not invoice.line_items and fields.line_items:
        invoice.line_items = [
            item.model_dump(mode="json") for item in fields.line_items
        ]

    # Combine validation warnings without duplicates
    existing_warnings = list(invoice.validation_warnings or [])
    for warning in extraction.validation_warnings:
        if warning not in existing_warnings:
            existing_warnings.append(warning)
    invoice.validation_warnings = existing_warnings

    if any("reconcile" in w.lower() for w in existing_warnings):
        invoice.review_status = "needs_review"


def _normalize_line_items(raw_items: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in raw_items:
        if isinstance(item, dict):
            desc = item.get("description", "")
            qty = item.get("quantity")
            price = item.get("unit_price", item.get("unitPrice"))
            rate = item.get("tax_rate", item.get("taxRate"))
            tax = item.get("tax_amount", item.get("taxAmount"))
            total = item.get("total_amount", item.get("total"))
            line = InvoiceLineItem(
                description=str(desc) if desc is not None else "",
                quantity=Decimal(str(qty)) if qty is not None and str(qty).strip() != "" else None,
                unit_price=Decimal(str(price)) if price is not None and str(price).strip() != "" else None,
                tax_rate=Decimal(str(rate)) if rate is not None and str(rate).strip() != "" else None,
                tax_amount=Decimal(str(tax)) if tax is not None and str(tax).strip() != "" else None,
                total_amount=Decimal(str(total)) if total is not None and str(total).strip() != "" else None,
            )
            normalized.append(line.model_dump(mode="json"))
        elif isinstance(item, InvoiceLineItem):
            normalized.append(item.model_dump(mode="json"))
    return normalized


def _invoice_to_read(invoice: Invoice) -> InvoiceRead:
    read = InvoiceRead.model_validate(invoice)
    if invoice.stored_filename:
        read.original_file_url = f"/invoices/{invoice.id}/file"
    return read


@router.post("/upload", response_model=InvoiceUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_invoice(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Validate uploaded invoice file, store safely, run OCR and extraction pipeline, and persist."""
    filename = file.filename or ""
    ext = Path(filename).suffix.lower()

    if ext not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{ext}'. Supported formats are: PDF, PNG, JPG, JPEG.",
        )

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    current_max_bytes = globals().get("MAX_UPLOAD_SIZE_BYTES", settings.max_upload_size_bytes)
    if len(content) > current_max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the maximum upload limit of {current_max_bytes // (1024 * 1024)}MB.",
        )

    expected_mime, magic_signature = SUPPORTED_FORMATS[ext]
    content_type = (file.content_type or "").lower().split(";")[0].strip()
    if content_type:
        if ext in (".jpg", ".jpeg"):
            valid_mimes = {"image/jpeg", "image/jpg", "image/pjpeg"}
        else:
            valid_mimes = {expected_mime}
        if content_type not in valid_mimes:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="File content type does not match its file extension.",
            )

    if not content.startswith(magic_signature):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="File contents do not match the expected file signature.",
        )

    current_uploads_dir = Path(globals().get("UPLOADS_DIR", settings.uploads_dir))
    current_uploads_dir.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{uuid.uuid4().hex}{ext}"
    file_path = current_uploads_dir / stored_filename
    file_path.write_bytes(content)

    invoice = Invoice(
        original_filename=filename,
        stored_filename=stored_filename,
        status="uploaded",
    )

    ocr_fn = globals().get("extract_text", ocr_extract_text)
    try:
        text = ocr_fn(file_path)
    except Exception:
        invoice.processing_status = "failed"
        invoice.review_status = "needs_review"
        invoice.validation_warnings = ["Automated document processing failed; manual entry or re-upload is required."]
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        return InvoiceUploadResponse(
            invoice_id=invoice.id,
            id=invoice.id,
            processing_status="failed",
            message="Document saved, but automated text extraction failed.",
        )

    invoice.extracted_text = text
    if not text or not text.strip():
        invoice.processing_status = "processed"
        invoice.review_status = "needs_review"
        invoice.validation_warnings = ["No readable text was recognized from the document; manual entry is required."]
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        return InvoiceUploadResponse(
            invoice_id=invoice.id,
            id=invoice.id,
            processing_status="processed",
            message="Document uploaded, but no readable text was recognized.",
        )

    extractor_fn = globals().get("extract_invoice_data", extraction_extract_invoice_data)
    extraction = extractor_fn(text)
    apply_fn = globals().get("_apply_extraction", _apply_extraction)
    apply_fn(invoice, extraction)
    invoice.processing_status = "processed"
    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    return InvoiceUploadResponse(
        invoice_id=invoice.id,
        id=invoice.id,
        processing_status="processed",
        message="Document uploaded and baseline invoice-field extraction completed.",
    )


@router.get("/export/json")
def export_invoices_json(db: Session = Depends(get_db)):
    """Export all invoices formatted as a JSON attachment."""
    invoices = list(db.scalars(select(Invoice).order_by(Invoice.id.asc())).all())
    invoice_reads = [InvoiceRead.model_validate(inv) for inv in invoices]
    content = export_service.export_invoices(invoice_reads, "json")
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="invoices.json"'},
    )


@router.get("/export/csv")
def export_invoices_csv(db: Session = Depends(get_db)):
    """Export all invoices formatted as a CSV attachment."""
    invoices = list(db.scalars(select(Invoice).order_by(Invoice.id.asc())).all())
    invoice_reads = [InvoiceRead.model_validate(inv) for inv in invoices]
    content = export_service.export_invoices(invoice_reads, "csv")
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="invoices.csv"'},
    )


@router.get("", response_model=list[InvoiceRead])
@router.get("/", response_model=list[InvoiceRead], include_in_schema=False)
def list_invoices(db: Session = Depends(get_db)):
    """Return all persisted invoices."""
    invoices = list(db.scalars(select(Invoice).order_by(Invoice.id.asc())).all())
    return [_invoice_to_read(inv) for inv in invoices]


@router.get("/{invoice_id}", response_model=InvoiceRead)
def get_invoice(invoice_id: int, db: Session = Depends(get_db)):
    """Retrieve full details for a single invoice."""
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found.",
        )
    return _invoice_to_read(invoice)


@router.get("/{invoice_id}/file")
def get_invoice_file(invoice_id: int, db: Session = Depends(get_db)):
    """Safely stream the source invoice document for preview."""
    invoice = db.get(Invoice, invoice_id)
    if not invoice or not invoice.stored_filename:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice document file not found.",
        )

    current_uploads_dir = Path(globals().get("UPLOADS_DIR", settings.uploads_dir)).resolve()
    file_path = (current_uploads_dir / invoice.stored_filename).resolve()

    if not file_path.is_relative_to(current_uploads_dir) or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice file does not exist on disk.",
        )

    ext = file_path.suffix.lower()
    media_type = SUPPORTED_FORMATS.get(ext, ("application/octet-stream", b""))[0]
    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=invoice.original_filename,
    )


@router.patch("/{invoice_id}", response_model=InvoiceRead)
def update_invoice(
    invoice_id: int,
    payload: InvoiceUpdate,
    db: Session = Depends(get_db),
):
    """Update fields of an existing invoice and persist corrections."""
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found.",
        )

    data = payload.model_dump(exclude_unset=True)

    if "invoice_number" in data:
        invoice.invoice_number = data["invoice_number"]
    elif "invoiceNumber" in data:
        invoice.invoice_number = data["invoiceNumber"]

    if "vendor_name" in data:
        invoice.vendor_name = data["vendor_name"]
    elif "vendor" in data and isinstance(data["vendor"], dict):
        if "name" in data["vendor"]:
            invoice.vendor_name = data["vendor"]["name"]

    if "vendor_address" in data:
        invoice.vendor_address = data["vendor_address"]
    elif "vendor" in data and isinstance(data["vendor"], dict):
        if "address" in data["vendor"]:
            invoice.vendor_address = data["vendor"]["address"]

    if "vendor_tax_id" in data:
        invoice.vendor_tax_id = data["vendor_tax_id"]
    elif "vendor" in data and isinstance(data["vendor"], dict):
        val = data["vendor"].get("taxId") or data["vendor"].get("tax_id")
        if val is not None:
            invoice.vendor_tax_id = val

    if "customer_name" in data:
        invoice.customer_name = data["customer_name"]
    elif "customer" in data and isinstance(data["customer"], dict):
        if "name" in data["customer"]:
            invoice.customer_name = data["customer"]["name"]

    if "customer_address" in data:
        invoice.customer_address = data["customer_address"]
    elif "customer" in data and isinstance(data["customer"], dict):
        if "address" in data["customer"]:
            invoice.customer_address = data["customer"]["address"]

    if "customer_tax_id" in data:
        invoice.customer_tax_id = data["customer_tax_id"]
    elif "customer" in data and isinstance(data["customer"], dict):
        val = data["customer"].get("taxId") or data["customer"].get("tax_id")
        if val is not None:
            invoice.customer_tax_id = val

    if "invoice_date" in data:
        invoice.invoice_date = data["invoice_date"]
    elif "invoiceDate" in data:
        invoice.invoice_date = data["invoiceDate"]

    if "due_date" in data:
        invoice.due_date = data["due_date"]
    elif "dueDate" in data:
        invoice.due_date = data["dueDate"]

    if "currency" in data:
        invoice.currency = data["currency"]

    if "payment_terms" in data:
        invoice.payment_terms = data["payment_terms"]
    elif "paymentTerms" in data:
        invoice.payment_terms = data["paymentTerms"]

    if "subtotal" in data:
        invoice.subtotal = data["subtotal"]

    if "tax_amount" in data:
        invoice.tax_amount = data["tax_amount"]
    elif "taxAmount" in data:
        invoice.tax_amount = data["taxAmount"]

    if "discount_amount" in data:
        invoice.discount_amount = data["discount_amount"]
    elif "discount" in data:
        invoice.discount_amount = data["discount"]
    elif "discountAmount" in data:
        invoice.discount_amount = data["discountAmount"]

    if "total_amount" in data:
        invoice.total_amount = data["total_amount"]
    elif "totalAmount" in data:
        invoice.total_amount = data["totalAmount"]

    if "amount_paid" in data:
        invoice.amount_paid = data["amount_paid"]
    elif "amountPaid" in data:
        invoice.amount_paid = data["amountPaid"]

    if "balance_due" in data:
        invoice.balance_due = data["balance_due"]
    elif "balanceDue" in data:
        invoice.balance_due = data["balanceDue"]

    if "line_items" in data and data["line_items"] is not None:
        invoice.line_items = _normalize_line_items(data["line_items"])
    elif "lineItems" in data and data["lineItems"] is not None:
        invoice.line_items = _normalize_line_items(data["lineItems"])

    invoice.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(invoice)
    return _invoice_to_read(invoice)


@router.post("/{invoice_id}/review", response_model=InvoiceRead)
def review_invoice(
    invoice_id: int,
    payload: InvoiceReviewRequest,
    db: Session = Depends(get_db),
):
    """Set the human review status for an invoice."""
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found.",
        )

    if payload.status not in VALID_REVIEW_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid review status '{payload.status}'. Must be one of: {', '.join(sorted(VALID_REVIEW_STATUSES))}.",
        )

    invoice.review_status = payload.status
    invoice.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(invoice)
    return _invoice_to_read(invoice)
