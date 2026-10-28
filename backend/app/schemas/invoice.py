from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

CURRENCY_CODES = {
    "AUD",
    "CAD",
    "CHF",
    "CNY",
    "EUR",
    "GBP",
    "INR",
    "JPY",
    "NZD",
    "USD",
}


class InvoiceLineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = Field(default="", max_length=1000)
    quantity: Decimal | None = Field(default=None, gt=0)
    unit_price: Decimal | None = Field(default=None, ge=0)
    tax_rate: Decimal | None = Field(default=None, ge=0)
    tax_amount: Decimal | None = Field(default=None, ge=0)
    total_amount: Decimal | None = Field(default=None, ge=0)


class InvoiceFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vendor_name: str | None = None
    vendor_address: str | None = None
    vendor_tax_id: str | None = None
    customer_name: str | None = None
    customer_address: str | None = None
    customer_tax_id: str | None = None
    invoice_number: str | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    payment_terms: str | None = None
    subtotal: Decimal | None = None
    tax_amount: Decimal | None = None
    discount_amount: Decimal | None = None
    total_amount: Decimal | None = None
    line_items: list[InvoiceLineItem] = Field(default_factory=list)

    @field_validator("currency")
    @classmethod
    def currency_must_be_uppercase_code(cls, value: str | None) -> str | None:
        if value is not None and value not in CURRENCY_CODES:
            raise ValueError("currency must be a supported three-letter uppercase code")
        return value


class InvoiceCreate(InvoiceFields):
    original_filename: str = Field(min_length=1, max_length=255)
    vendor_address: str | None = None
    vendor_tax_id: str | None = None
    customer_name: str | None = None
    customer_address: str | None = None
    customer_tax_id: str | None = None
    payment_terms: str | None = None
    amount_paid: Decimal | None = None
    balance_due: Decimal | None = None

    @field_validator("original_filename")
    @classmethod
    def filename_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("original_filename must not be blank")
        return value


class InvoiceRead(InvoiceCreate):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: int
    extracted_text: str | None = None
    source_format: str | None = None
    confidence: dict[str, float] | None = None
    n8n_validation: dict[str, Any] | None = None
    ai_analysis: dict[str, Any] | None = None
    processing_status: str = "placeholder"
    review_status: str = "pending"
    status: str = "uploaded"
    validation_warnings: list[Any] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    original_file_url: str | None = None


class InvoiceUploadResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    invoice_id: int
    id: int
    processing_status: str
    message: str
    invoice_ids: list[int] = Field(default_factory=list)
    invoice_count: int = 1


class InvoiceReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(min_length=1, max_length=50)


class InvoiceUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    vendor_name: str | None = None
    vendor_address: str | None = None
    vendor_tax_id: str | None = None
    customer_name: str | None = None
    customer_address: str | None = None
    customer_tax_id: str | None = None
    invoice_number: str | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    currency: str | None = None
    payment_terms: str | None = None
    subtotal: Decimal | None = None
    tax_amount: Decimal | None = None
    discount_amount: Decimal | None = None
    total_amount: Decimal | None = None
    amount_paid: Decimal | None = None
    balance_due: Decimal | None = None
    line_items: list[dict[str, Any]] | list[Any] | None = None

    # Alternative/frontend camelCase keys
    vendor: dict[str, Any] | None = None
    customer: dict[str, Any] | None = None
    discount: Decimal | None = None
    discountAmount: Decimal | None = None
    invoiceNumber: str | None = None
    invoiceDate: date | None = None
    dueDate: date | None = None
    paymentTerms: str | None = None
    taxAmount: Decimal | None = None
    totalAmount: Decimal | None = None
    amountPaid: Decimal | None = None
    balanceDue: Decimal | None = None
    lineItems: list[dict[str, Any]] | list[Any] | None = None
