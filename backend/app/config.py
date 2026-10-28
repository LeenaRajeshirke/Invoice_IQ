import os
from dataclasses import dataclass
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]


def _cors_origins() -> tuple[str, ...]:
    configured = os.getenv("INVOICEIQ_CORS_ORIGINS")
    if configured:
        return tuple(origin.strip() for origin in configured.split(",") if origin.strip())
    return (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5000",
    )


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv(
        "INVOICEIQ_DATABASE_URL",
        f"sqlite:///{(BACKEND_DIR / 'data' / 'invoiceiq.sqlite3').as_posix()}",
    )
    uploads_dir: Path = Path(
        os.getenv("INVOICEIQ_UPLOADS_DIR", str(BACKEND_DIR / "data" / "uploads"))
    )
    max_upload_size_bytes: int = int(os.getenv("INVOICEIQ_MAX_UPLOAD_MB", "10")) * 1024 * 1024
    cors_origins: tuple[str, ...] = _cors_origins()
    n8n_invoice_webhook_url: str | None = os.getenv("N8N_INVOICE_WEBHOOK_URL")
    n8n_invoice_webhook_secret: str | None = os.getenv("N8N_INVOICE_WEBHOOK_SECRET")


settings = Settings()
