import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx

from app.schemas.invoice import InvoiceFields
from app.services import n8n_service
from app.services.n8n_service import (
    N8NIntegrationError,
    build_invoice_payload,
    call_invoice_workflow,
    parse_n8n_response,
)


class N8NServiceTests(unittest.TestCase):
    def test_payload_normalizes_invoice_and_preserves_financial_values(self) -> None:
        payload = build_invoice_payload(
            7,
            "csv",
            "records.csv",
            InvoiceFields(
                invoice_number="INV-7",
                vendor_name="Example Vendor",
                invoice_date="2026-10-12",
                currency="USD",
                subtotal="100.00",
                tax_amount="8.00",
                discount_amount="5.00",
                total_amount="103.00",
            ),
        )

        self.assertEqual(payload["event"], "invoice.uploaded")
        self.assertEqual(payload["invoice_id"], 7)
        self.assertEqual(payload["source_format"], "csv")
        self.assertEqual(payload["file_name"], "records.csv")
        self.assertEqual(
            payload["invoices"][0],
            {
                "vendor_name": "Example Vendor",
                "vendor_address": None,
                "vendor_tax_id": None,
                "customer_name": None,
                "customer_address": None,
                "customer_tax_id": None,
                "invoice_number": "INV-7",
                "invoice_date": "2026-10-12",
                "due_date": None,
                "currency": "USD",
                "payment_terms": None,
                "subtotal": 100.0,
                "tax": 8.0,
                "discount": 5.0,
                "total": 103.0,
            },
        )

    def test_parser_decodes_gemini_json_returned_as_text(self) -> None:
        validation, analysis, warnings, valid = parse_n8n_response(
            {
                "validation": {"status": "valid", "errors": [], "warnings": ["Verify PO number"]},
                "output": '{"risk_level":"MEDIUM","findings":["Tax rate differs"],"explanation":"Review tax."}',
            }
        )

        self.assertTrue(valid)
        self.assertEqual(validation["status"], "valid")
        self.assertEqual(analysis["risk_level"], "MEDIUM")
        self.assertEqual(analysis["findings"], ["Tax rate differs"])
        self.assertEqual(warnings, ["Verify PO number"])

    def test_parser_accepts_invalid_branch_without_ai_output(self) -> None:
        validation, analysis, _, valid = parse_n8n_response(
            {
                "validation": {
                    "valid": False,
                    "errors": ["Invoice number is missing."],
                    "warnings": [],
                }
            }
        )

        self.assertFalse(valid)
        self.assertIsNone(analysis)
        self.assertEqual(validation["status"], "invalid")

    def test_malformed_gemini_json_is_not_reported_as_successful_analysis(self) -> None:
        validation, analysis, _, valid = parse_n8n_response(
            {
                "validation": {"status": "valid", "errors": [], "warnings": []},
                "output": "not JSON",
            }
        )

        self.assertTrue(valid)
        self.assertEqual(analysis["risk_level"], "UNKNOWN")
        self.assertEqual(analysis["raw_output"], "not JSON")

    def test_http_request_uses_configured_auth_header_and_parses_json(self) -> None:
        response = Mock()
        response.is_success = True
        response.json.return_value = {
            "validation": {"status": "valid", "errors": [], "warnings": []},
            "ai_analysis": {
                "risk_level": "LOW",
                "findings": [],
                "explanation": "No anomalies.",
            },
        }
        config = SimpleNamespace(
            n8n_invoice_webhook_url="http://n8n.internal/webhook/test",
            n8n_invoice_webhook_secret="test-secret",
        )
        with (
            patch.object(n8n_service, "settings", config),
            patch.object(n8n_service.httpx, "post", return_value=response) as post,
        ):
            result = call_invoice_workflow({"invoice_id": 12})

        self.assertTrue(result[3])
        self.assertEqual(result[1]["risk_level"], "LOW")
        self.assertEqual(post.call_args.kwargs["headers"], {"X-Webhook-Secret": "test-secret"})
        self.assertEqual(post.call_args.kwargs["json"], {"invoice_id": 12})
        self.assertEqual(post.call_args.kwargs["timeout"], n8n_service.N8N_TIMEOUT_SECONDS)

    def test_timeout_and_authentication_errors_are_explicit(self) -> None:
        config = SimpleNamespace(
            n8n_invoice_webhook_url="http://n8n.internal/webhook/test",
            n8n_invoice_webhook_secret="test-secret",
        )
        request = httpx.Request("POST", config.n8n_invoice_webhook_url)
        with (
            patch.object(n8n_service, "settings", config),
            patch.object(n8n_service.httpx, "post", side_effect=httpx.TimeoutException("timeout", request=request)),
        ):
            with self.assertRaisesRegex(N8NIntegrationError, "timed out"):
                call_invoice_workflow({})

        with patch.object(
            n8n_service,
            "settings",
            SimpleNamespace(n8n_invoice_webhook_url=config.n8n_invoice_webhook_url, n8n_invoice_webhook_secret=None),
        ):
            with self.assertRaisesRegex(N8NIntegrationError, "N8N_INVOICE_WEBHOOK_SECRET"):
                call_invoice_workflow({})

    def test_non_successful_http_response_is_not_hidden(self) -> None:
        response = Mock()
        response.is_success = False
        response.status_code = 401
        config = SimpleNamespace(
            n8n_invoice_webhook_url="http://n8n.internal/webhook/test",
            n8n_invoice_webhook_secret="test-secret",
        )
        with (
            patch.object(n8n_service, "settings", config),
            patch.object(n8n_service.httpx, "post", return_value=response),
        ):
            with self.assertRaisesRegex(N8NIntegrationError, "HTTP 401"):
                call_invoice_workflow({})


if __name__ == "__main__":
    unittest.main()
