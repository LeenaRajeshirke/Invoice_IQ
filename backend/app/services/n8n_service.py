import json
from typing import Any

import httpx

from app.config import settings
from app.schemas.invoice import InvoiceFields

N8N_TIMEOUT_SECONDS = 20.0


class N8NIntegrationError(RuntimeError):
    """The configured n8n workflow could not be called or returned unusable data."""


def build_invoice_payload(
    invoice_id: int,
    source_format: str,
    file_name: str,
    fields: InvoiceFields,
) -> dict[str, Any]:
    invoice = fields.model_dump(mode="json")
    invoice["tax"] = invoice.pop("tax_amount")
    invoice["total"] = invoice.pop("total_amount")
    invoice.pop("line_items", None)
    amount_fields = {
        "subtotal": fields.subtotal,
        "tax": fields.tax_amount,
        "total": fields.total_amount,
    }
    if "discount_amount" in invoice:
        invoice["discount"] = invoice.pop("discount_amount")
        amount_fields["discount"] = fields.discount_amount
    for amount_name, amount in amount_fields.items():
        if amount_name in invoice or amount_name in {"subtotal", "tax", "total"}:
            invoice[amount_name] = float(amount) if amount is not None else None
    return {
        "event": "invoice.uploaded",
        "invoice_id": invoice_id,
        "source_format": source_format,
        "file_name": file_name,
        "invoices": [invoice],
    }


def _decode_ai_result(value: Any) -> dict[str, Any] | None:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return {
                "risk_level": "UNKNOWN",
                "findings": [],
                "explanation": "AI analysis returned text that could not be parsed as structured results.",
                "raw_output": value,
            }
    if isinstance(value, dict):
        return {
            "risk_level": str(value.get("risk_level", value.get("riskLevel", "UNKNOWN"))).upper(),
            "findings": value.get("findings", []) if isinstance(value.get("findings", []), list) else [],
            "explanation": str(value.get("explanation", value.get("summary", ""))),
            **({"raw_output": value.get("raw_output")} if value.get("raw_output") is not None else {}),
        }
    return None


def _find_ai_result(response: Any) -> dict[str, Any] | None:
    if isinstance(response, list):
        for item in response:
            found = _find_ai_result(item)
            if found:
                return found
        return None
    if not isinstance(response, dict):
        return None
    for key in ("ai_analysis", "aiAnalysis", "analysis", "output", "text", "response"):
        if key in response:
            decoded = _decode_ai_result(response[key])
            if decoded is not None:
                return decoded
    for key in ("data", "result", "body"):
        if key in response:
            found = _find_ai_result(response[key])
            if found:
                return found
    return None


def parse_n8n_response(response: Any) -> tuple[dict[str, Any], dict[str, Any] | None, list[str], bool]:
    """Extract deterministic validation independently from any Gemini-generated result."""
    if isinstance(response, str):
        try:
            response = json.loads(response)
        except json.JSONDecodeError as error:
            raise N8NIntegrationError("The n8n workflow returned invalid JSON.") from error
    if isinstance(response, list) and len(response) == 1:
        response = response[0]
    if not isinstance(response, dict):
        raise N8NIntegrationError("The n8n workflow returned an unexpected response structure.")

    validation: Any = response.get(
        "validation",
        response.get("validation_result", response.get("validationResult")),
    )
    if validation is None:
        validation = response.get("data", {}).get("validation") if isinstance(response.get("data"), dict) else None
    if isinstance(validation, str):
        try:
            validation = json.loads(validation)
        except json.JSONDecodeError as error:
            raise N8NIntegrationError("The n8n workflow returned invalid validation JSON.") from error
    if not isinstance(validation, dict):
        raise N8NIntegrationError("The n8n workflow response is missing deterministic validation results.")

    errors = validation.get("errors") or []
    warnings = validation.get("warnings") or []
    errors = errors if isinstance(errors, list) else [str(errors)]
    warnings = warnings if isinstance(warnings, list) else [str(warnings)]
    reported_status = validation.get("status")
    if reported_status is None:
        reported_valid = validation.get("valid", validation.get("isValid"))
        reported_status = (
            "valid" if reported_valid is True else "invalid" if reported_valid is False else
            "invalid" if errors else "valid"
        )
    normalized_validation = {
        "status": str(reported_status).lower(),
        "errors": errors,
        "warnings": warnings,
    }
    valid = normalized_validation["status"] in {"valid", "passed", "success", "processed", "ok"} and not errors

    ai_analysis = _find_ai_result(response)
    if ai_analysis is None and valid:
        raise N8NIntegrationError("The n8n workflow response is missing Gemini analysis output.")
    return normalized_validation, ai_analysis, [str(item) for item in warnings], valid


def call_invoice_workflow(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None, list[str], bool]:
    url = settings.n8n_invoice_webhook_url
    secret = settings.n8n_invoice_webhook_secret
    if not url:
        raise N8NIntegrationError("n8n invoice processing is not configured. Set N8N_INVOICE_WEBHOOK_URL.")
    if not secret:
        raise N8NIntegrationError("n8n authentication is not configured. Set N8N_INVOICE_WEBHOOK_SECRET.")

    try:
        response = httpx.post(
            url,
            json=payload,
            headers={"X-Webhook-Secret": secret},
            timeout=N8N_TIMEOUT_SECONDS,
        )
    except httpx.TimeoutException as error:
        raise N8NIntegrationError("The n8n invoice workflow timed out.") from error
    except httpx.RequestError as error:
        raise N8NIntegrationError("The n8n invoice workflow could not be reached.") from error
    if not response.is_success:
        raise N8NIntegrationError(
            f"The n8n invoice workflow returned HTTP {response.status_code}."
        )
    try:
        result = response.json()
    except (ValueError, json.JSONDecodeError) as error:
        raise N8NIntegrationError("The n8n invoice workflow returned invalid JSON.") from error
    return parse_n8n_response(result)
