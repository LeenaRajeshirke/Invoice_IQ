from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Date, DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    source_format: Mapped[str | None] = mapped_column(String(10), nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vendor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vendor_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    vendor_tax_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_tax_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    payment_terms: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    discount_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    amount_paid: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    balance_due: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    line_items: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    confidence: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    validation_warnings: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    n8n_validation: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    ai_analysis: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="uploaded", nullable=False)
    processing_status: Mapped[str] = mapped_column(
        String(30), default="placeholder", nullable=False
    )
    review_status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, onupdate=_utc_now
    )
