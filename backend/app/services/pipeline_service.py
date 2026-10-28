from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from app.schemas.invoice import InvoiceFields
from app.services.extraction_service import extract_invoice_data
from app.services.ocr_service import extract_document
from app.services.validation_service import (
    ValidationWarning,
    validate_extracted_invoice,
)


class InvoiceProcessingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: InvoiceFields
    warnings: list[ValidationWarning]
    ocr_source: str
    ocr_mean_token_confidence: float | None = None


def process_invoice_document(
    file_path: Path,
    existing_invoices: Iterable[InvoiceFields | dict[str, object]] = (),
) -> InvoiceProcessingResult:
    """Run OCR, rule extraction, and non-mutating validation for one document."""
    ocr_result = extract_document(file_path)
    extraction = extract_invoice_data(ocr_result.text)
    warnings = validate_extracted_invoice(
        extraction.fields,
        extraction_warnings=extraction.validation_warnings,
        existing_invoices=existing_invoices,
    )
    warnings.extend(
        ValidationWarning(
            field=None,
            code="ocr_unreadable_content",
            severity="warning",
            message=message,
        )
        for message in ocr_result.warnings
    )
    return InvoiceProcessingResult(
        fields=extraction.fields,
        warnings=warnings,
        ocr_source=ocr_result.source,
        ocr_mean_token_confidence=ocr_result.mean_token_confidence,
    )
