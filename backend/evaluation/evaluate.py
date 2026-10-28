"""Benchmark and evaluation suite for InvoiceIQ AI Pipeline.

Measures per-field accuracy, line-item accuracy, full-invoice exact match,
arithmetic consistency detection rate, and processing latency.
"""
from dataclasses import dataclass, field
import argparse
from decimal import Decimal
import json
from pathlib import Path
import sys
import time
from typing import Any

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.services.pipeline_service import process_invoice_document


def _normalize_str(val: Any) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    return s.lower() if s else None


def _normalize_num(val: Any) -> Decimal | None:
    if val is None or val == "":
        return None
    try:
        return Decimal(str(val)).quantize(Decimal("0.01"))
    except Exception:
        return None


def run_evaluation(
    samples_dir: Path | None = None,
    ground_truth_path: Path | None = None,
    report_path: Path | None = None,
) -> dict[str, Any]:
    eval_dir = Path(__file__).resolve().parent
    samples_dir = samples_dir or eval_dir / "samples"
    gt_path = ground_truth_path or eval_dir / "ground_truth.json"

    with open(gt_path, "r", encoding="utf-8") as f:
        ground_truth: dict[str, Any] = json.load(f)

    field_names = [
        "vendor_name",
        "invoice_number",
        "invoice_date",
        "due_date",
        "currency",
        "subtotal",
        "tax_amount",
        "discount_amount",
        "total_amount",
    ]

    field_correct: dict[str, int] = {f: 0 for f in field_names}
    field_total: dict[str, int] = {f: 0 for f in field_names}
    full_invoice_exact = 0
    total_line_items_expected = 0
    total_line_items_matched = 0
    arithmetic_correct_eval = 0
    total_samples = len(ground_truth)

    results: list[dict[str, Any]] = []
    timings: dict[str, list[float]] = {"digital_pdf": [], "ocr_scanned": []}

    print("=" * 80)
    print("INVOICEIQ AI PIPELINE EVALUATION BENCHMARK")
    print(f"Sample Size: {total_samples} diverse documents")
    print("=" * 80)

    for filename, expected in ground_truth.items():
        sample_path = samples_dir / filename
        file_type = expected["file_type"]

        start_time = time.perf_counter()
        pipeline_result = process_invoice_document(sample_path)
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        timing_category = "digital_pdf" if file_type == "digital_pdf" else "ocr_scanned"
        timings[timing_category].append(elapsed_ms)

        extracted_fields = pipeline_result.fields
        warnings = [w.message for w in pipeline_result.warnings]
        warning_codes = [w.code for w in pipeline_result.warnings]

        sample_eval: dict[str, Any] = {
            "filename": filename,
            "file_type": file_type,
            "ocr_source": pipeline_result.ocr_source,
            "latency_ms": round(elapsed_ms, 2),
            "token_confidence": pipeline_result.ocr_mean_token_confidence,
            "field_matches": {},
            "all_fields_matched": True,
            "warnings": warnings,
        }

        # Check each field
        for field in field_names:
            exp_val = expected.get(field)
            act_val = getattr(extracted_fields, field, None)

            field_total[field] += 1

            matched = False
            if field in ("subtotal", "tax_amount", "discount_amount", "total_amount"):
                exp_num = _normalize_num(exp_val)
                act_num = _normalize_num(act_val)
                matched = (exp_num == act_num)
            elif field in ("invoice_date", "due_date"):
                exp_date = str(exp_val) if exp_val is not None else None
                act_date = str(act_val) if act_val is not None else None
                matched = (exp_date == act_date)
            else:
                matched = (_normalize_str(exp_val) == _normalize_str(act_val))

            sample_eval["field_matches"][field] = {
                "expected": exp_val,
                "actual": str(act_val) if act_val is not None else None,
                "matched": matched,
            }

            if matched:
                field_correct[field] += 1
            else:
                sample_eval["all_fields_matched"] = False

        # Line items evaluation
        exp_lines = expected.get("line_items", [])
        act_lines = extracted_fields.line_items
        total_line_items_expected += len(exp_lines)

        matched_lines_count = 0
        for exp_item in exp_lines:
            found = False
            for act_item in act_lines:
                desc_match = _normalize_str(exp_item["description"]) in _normalize_str(act_item.description) or _normalize_str(act_item.description) in _normalize_str(exp_item["description"])
                qty_match = _normalize_num(exp_item["quantity"]) == _normalize_num(act_item.quantity)
                price_match = _normalize_num(exp_item["unit_price"]) == _normalize_num(act_item.unit_price)
                if desc_match and qty_match and price_match:
                    found = True
                    break
            if found:
                matched_lines_count += 1

        total_line_items_matched += matched_lines_count
        sample_eval["line_items_accuracy"] = (
            1.0 if not exp_lines and not act_lines else (matched_lines_count / len(exp_lines) if exp_lines else 0.0)
        )
        if len(act_lines) != len(exp_lines) or matched_lines_count != len(exp_lines):
            sample_eval["all_fields_matched"] = False

        # Arithmetic Consistency Check
        exp_consistent = expected["arithmetic_consistent"]
        has_mismatch_warning = any(
            "reconcile" in w.lower() or "amount_mismatch" in code for w, code in zip(warnings, warning_codes)
        )
        act_consistent = not has_mismatch_warning
        arithmetic_matched = (exp_consistent == act_consistent)
        if arithmetic_matched:
            arithmetic_correct_eval += 1
        sample_eval["arithmetic_consistent_detected"] = arithmetic_matched

        if sample_eval["all_fields_matched"]:
            full_invoice_exact += 1

        results.append(sample_eval)

        status_str = "PASS" if sample_eval["all_fields_matched"] else "PARTIAL/WARN"
        print(f"[{status_str}] {filename} ({file_type}) - {elapsed_ms:.1f}ms - OCR: {pipeline_result.ocr_source}")

    # Aggregated metrics
    field_accuracy = {f: round((field_correct[f] / field_total[f]) * 100, 1) for f in field_names}
    line_item_accuracy = round((total_line_items_matched / total_line_items_expected * 100), 1) if total_line_items_expected else 100.0
    full_invoice_accuracy = round((full_invoice_exact / total_samples) * 100, 1)
    arithmetic_eval_accuracy = round((arithmetic_correct_eval / total_samples) * 100, 1)

    avg_digital_lat = sum(timings["digital_pdf"]) / len(timings["digital_pdf"]) if timings["digital_pdf"] else 0.0
    avg_ocr_lat = sum(timings["ocr_scanned"]) / len(timings["ocr_scanned"]) if timings["ocr_scanned"] else 0.0

    report = {
        "sample_size": total_samples,
        "categories": {
            "digital_pdf_count": len(timings["digital_pdf"]),
            "ocr_scanned_and_image_count": len(timings["ocr_scanned"]),
        },
        "per_field_accuracy_pct": field_accuracy,
        "line_item_accuracy_pct": line_item_accuracy,
        "full_invoice_exact_match_pct": full_invoice_accuracy,
        "arithmetic_consistency_detection_pct": arithmetic_eval_accuracy,
        "latency_ms": {
            "digital_pdf_mean": round(avg_digital_lat, 1),
            "ocr_scanned_mean": round(avg_ocr_lat, 1),
        },
        "detailed_results": results,
    }

    report_path = report_path or eval_dir / "evaluation_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("\n" + "=" * 80)
    print("ACCURACY SUMMARY")
    print("=" * 80)
    for field, acc in field_accuracy.items():
        print(f"  {field.ljust(22)}: {acc}% ({field_correct[field]}/{field_total[field]})")
    print(f"  {'line_items'.ljust(22)}: {line_item_accuracy}% ({total_line_items_matched}/{total_line_items_expected})")
    print("-" * 80)
    print(f"Full-Invoice Exact Match: {full_invoice_accuracy}% ({full_invoice_exact}/{total_samples})")
    print(f"Arithmetic Consistency Detection Rate: {arithmetic_eval_accuracy}% ({arithmetic_correct_eval}/{total_samples})")
    print("-" * 80)
    print(f"Digital PDF Mean Latency : {avg_digital_lat:.1f}ms (Fast - text extraction directly from PyMuPDF)")
    print(f"OCR/Scanned Mean Latency: {avg_ocr_lat:.1f}ms (CPU inference via RapidOCR/ONNX)")
    print("=" * 80)
    print(f"Saved complete evaluation report to {report_path}")

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate InvoiceIQ invoice samples.")
    parser.add_argument("--samples-dir", type=Path, help="Directory containing invoice files.")
    parser.add_argument("--ground-truth", type=Path, help="Path to ground_truth.json.")
    parser.add_argument("--report", type=Path, help="Where to write the evaluation report.")
    args = parser.parse_args()
    run_evaluation(args.samples_dir, args.ground_truth, args.report)
