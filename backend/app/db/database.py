from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()


def _migrate_existing_invoice_table() -> None:
    """Add fields introduced after the initial invoice schema."""
    inspector = inspect(engine)
    if "invoices" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("invoices")}
    additions = {
        "discount_amount": "NUMERIC(12, 2)",
        "content_sha256": "VARCHAR(64)",
        "source_format": "VARCHAR(10)",
        "n8n_validation": "JSON",
        "ai_analysis": "JSON",
    }
    with engine.begin() as connection:
        for column, sql_type in additions.items():
            if column not in columns:
                connection.execute(
                    text(f"ALTER TABLE invoices ADD COLUMN {column} {sql_type}")
                )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_invoices_content_sha256 ON invoices (content_sha256)"
            )
        )


def init_db() -> None:
    from app.db import models  # noqa: F401

    if settings.database_url.startswith("sqlite:///"):
        from pathlib import Path

        Path(settings.database_url.removeprefix("sqlite:///")).parent.mkdir(
            parents=True, exist_ok=True
        )
    Base.metadata.create_all(bind=engine)
    _migrate_existing_invoice_table()
