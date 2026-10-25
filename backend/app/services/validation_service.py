from app.schemas.invoice import InvoiceCreate


def validate_invoice_data(data: dict[str, object]) -> InvoiceCreate:
    """Business-validation interface for future extracted invoice data."""
    raise NotImplementedError("Invoice business validation has not been implemented")