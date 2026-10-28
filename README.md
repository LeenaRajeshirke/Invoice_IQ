# InvoiceIQ — AI-Powered Invoice Understanding and Information Extraction

InvoiceIQ is an end-to-end intelligent document processing application designed for invoice intake, OCR extraction, structured data extraction, automated validation, human-in-the-loop review, and standardized export.

The system features a **React + Vite** SaaS interface (developed by Leena), a **FastAPI + SQLAlchemy + SQLite** backend (developed by Dinesh), and a hybrid **OCR & pattern-based AI extraction pipeline**.

---

## 1. Quick Start & Verified Installation

### Prerequisites
- **Node.js**: v18+ (tested on v24.20.0) and **npm**
- **Python**: 3.10–3.14 (tested on 3.14.4)

### A. Backend Setup

```bash
cd backend

# 1. Install dependencies
python -m pip install -r requirements.txt

# 2. Start the FastAPI backend server (port 8000)
python -m uvicorn app.main:app --reload --port 8000
```

The database automatically initializes at `backend/data/invoiceiq.sqlite3` on startup. Uploaded documents are securely saved to the private directory `backend/data/uploads/` (never exposed as public static files).

### B. Frontend Setup

From the root project directory:

```bash
# 1. Install dependencies
npm install

# 2. Configure environment (points to live FastAPI backend)
# .env is already configured with:
# VITE_API_MODE=live
# VITE_API_BASE_URL=http://localhost:8000
# VITE_MAX_UPLOAD_MB=10

# 3. Start Vite development server (port 5173)
npm run dev
```

Open `http://localhost:5173` in your browser.

To run a production build:
```bash
npm run build
npm run preview
```

---

## 2. Test Execution & Verification

Both the backend and frontend include automated test suites.

### Backend Test Suite (65 Unit & Integration Tests)
From the `backend/` directory:
```bash
python -m unittest discover -s tests
```
*Covers database models, FastAPI routes, OCR services, extraction rules, validation logic, end-to-end upload-to-review lifecycle, and runtime crash guards (65 passed).*

### Frontend Test Suite (11 Unit Tests)
From the project root:
```bash
npm test
```
*Covers bidirectional snake_case $\leftrightarrow$ camelCase data mapping, status aliasing, upload wrappers, and API client methods (11 passed).*

### Pipeline Benchmark Evaluation
From the project root:
```bash
python backend/evaluation/evaluate.py
```
*Evaluates the AI extraction pipeline across 8 diverse benchmark invoices against independent ground truth metadata.*

### Generate and Evaluate Additional Synthetic Invoices
Generate a separate, reproducible dataset without overwriting the original benchmark:
```bash
python backend/evaluation/generate_synthetic_dataset.py
python backend/evaluation/evaluate.py --samples-dir backend/evaluation/synthetic_dataset --ground-truth backend/evaluation/synthetic_dataset/ground_truth.json --report backend/evaluation/synthetic_dataset/evaluation_report.json
```
The generated dataset contains 20 digital PDFs plus PNG, JPEG, and scanned-PDF samples, with ground truth and source text. Two digital samples intentionally contain reconciliation errors for validation testing. OCR-based samples are useful as upload smoke tests; OCR success depends on the installed runtime and should be assessed separately from digital-PDF extraction.

---

## 3. Architecture & Data Flow

```text
[ Document Intake ] ──► [ Security Validation ] ──► [ Text Extraction ]
 (.pdf, .png, .jpg)      (Magic bytes & size)        (PyMuPDF / RapidOCR)
                                                               │
                                                               ▼
[ SQLite Storage ]  ◄── [ Validation Engine ]   ◄── [ Rule Extraction ]
 (Private uploads)       (Arithmetic checks)         (Vendor, Dates, Items)
        │
        ▼
[ FastAPI Endpoints ] ──► [ Frontend Mapper ]   ──► [ Human Review ] ──► [ CSV/JSON Export ]
 (/invoices/upload)        (snake ◄► camelCase)      (Review.jsx edits)   (Clean data out)
```

1. **Document Intake & Validation**:
   Uploaded files are validated in-memory before writing to disk. The server verifies magic byte signatures (`%PDF-`, `\x89PNG\r\n\x1a\n`, `\xff\xd8\xff`), MIME types, file sizes ($\le 10$ MB), and non-empty content. Rejected uploads return `400`, `413`, or `415` without persisting artifacts.
2. **Text Extraction**:
   - **Digital PDFs**: PyMuPDF (`fitz`) extracts embedded character streams natively ($\approx 5$ ms latency).
   - **Scanned PDFs & Images**: Routed to RapidOCR (ONNX runtime) for optical character recognition.
3. **Structured Extraction**:
   Rule- and regex-based entity extraction identifies vendor/customer details, tax identifiers, invoice numbers, currency codes, dates, financial amounts, and line-item rows.
4. **Validation & Reconciliation**:
   Checks whether $\text{subtotal} - \text{discount} + \text{tax} = \text{total}$. Flags arithmetic discrepancies, missing mandatory fields, and inverted dates as non-mutating warnings.
5. **Persistence**:
   Records are persisted in SQLite with statuses (`processing_status: "processed"`, `review_status: "pending"` or `"needs_review"`). Files are stored under UUID4 hexadecimal filenames (`[0-9a-f]{32}\.<ext>`).
6. **Human-in-the-Loop Review**:
   Reviewers inspect the source preview side-by-side, correct ambiguous values, adjust line items, and approve/reject the invoice. Edits are sent via `PATCH /invoices/{id}` and persist across page reloads.

---

## 4. What is AI/ML vs. Deterministic Processing?

To maintain academic and technical integrity, the project distinguishes between learned machine learning models and deterministic code:

| Component | Technique | Category |
| :--- | :--- | :---: |
| **Raster OCR Detection** | DBNet (Real-time Scene Text Detection) via ONNX Runtime | **AI / Machine Learning** |
| **Raster OCR Recognition** | SVTR (Single Visual Model for Text Recognition) via ONNX Runtime | **AI / Machine Learning** |
| **OCR Confidence Scoring** | Model token-level classification confidence scores | **AI / Machine Learning** |
| **Digital PDF Extraction** | PyMuPDF direct PDF font stream decoding | **Deterministic Parser** |
| **Entity & Field Parsing** | Regex pattern matching and label boundary state machine | **Deterministic Rules** |
| **Validation & Reconciliation** | Decimal arithmetic verification and date ordering constraints | **Deterministic Rules** |
| **Data Mapping & Persistence** | Pydantic schema validation and SQLAlchemy ORM | **Software Engineering** |

*Note: High/Moderate confidence badges in the UI reflect model token diagnostics, not statistical certainty of extraction accuracy. Arithmetic checks surface validation warnings for human review, not automated fraud proof.*

---

## 5. API Contract Reference

The backend exposes a standardized **snake_case** REST API:

| Method | Endpoint | Description | Status Codes |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Health probe | `200` |
| `POST` | `/invoices/upload` | Multipart file upload (`file` field) $\rightarrow$ OCR $\rightarrow$ extraction | `201`, `400`, `413`, `415` |
| `GET` | `/invoices` | List all persisted invoices | `200` |
| `GET` | `/invoices/{id}` | Retrieve complete invoice detail | `200`, `404` |
| `PATCH` | `/invoices/{id}` | Update invoice fields and persist corrections | `200`, `404` |
| `POST` | `/invoices/{id}/review` | Update review status (`reviewed`, `needs_review`, `rejected`) | `200`, `400`, `404` |
| `GET` | `/invoices/{id}/file` | Secure document stream for preview | `200`, `404` |
| `GET` | `/invoices/export/json` | Export all invoices as a JSON attachment | `200` |
| `GET` | `/invoices/export/csv` | Export all invoices as a CSV attachment | `200` |

---

## 6. Measured Evaluation Results (Benchmark)

Evaluated against 8 synthetic, non-sensitive sample invoices in [`backend/evaluation/`](file:///c:/Users/MR.%20JEET/Downloads/Invoice_IQ-main/backend/evaluation):

- **Sample Size**: 8 documents (5 digital vector PDFs, 1 scanned PDF, 1 PNG, 1 JPEG).
- **Per-Field Accuracy on Digital PDFs**: **100.0%** (vendor name, invoice number, dates, currency, subtotal, tax, discount, total).
- **Line-Item Extraction on Digital PDFs**: **100.0%** (all line items accurately parsed).
- **Arithmetic Inconsistency Detection**: **100.0%** (mathematical discrepancies accurately flagged for human review).
- **Digital PDF Processing Latency**: **5.1 ms** mean execution time.
- **Overall Exact Match across All Samples**: **62.5%** (5/8 full exact matches).

---

## 7. Security & Privacy Considerations

1. **File Validation & Magic Byte Defense**:
   Files are validated by magic byte signatures, not just file extensions. Uploads with mismatched content types or spoofed extensions are rejected with `415 Unsupported Media Type`.
2. **Private Document Storage**:
   Uploaded files are stored outside the web root in `backend/data/uploads/` using 32-character random hexadecimal UUIDs. The upload directory is never mounted as public static content.
3. **Path Traversal Protection**:
   The `/invoices/{id}/file` preview endpoint verifies that resolved file paths reside strictly within the uploads directory (`is_relative_to`), preventing directory traversal attacks (`../../`).
4. **Error Sanitization**:
   Internal file paths, database connection strings, stack traces, and private OCR engine details are stripped before returning error responses to the client.
5. **Authentication & Authorization (Academic Disclosure)**:
   This mini-project currently operates in workspace single-tenant mode without production-grade authentication (e.g. JWT/OAuth2) or role-based access control. In a production deployment, an API gateway and auth middleware must be added before handling sensitive financial records.

---

## 8. College Project Demonstration Checklist

Follow this workflow to demonstrate the application to evaluators:

1. **Health & Connectivity**:
   - Navigate to **Settings** (`/settings`) $\rightarrow$ verify green **API connected** indicator (`http://localhost:8000`).
2. **Clean Digital Invoice Ingestion**:
   - Go to **Upload invoice** (`/upload`) $\rightarrow$ upload a digital PDF (e.g. [`backend/evaluation/samples/inv_01_digital_standard.pdf`](file:///c:/Users/MR.%20JEET/Downloads/Invoice_IQ-main/backend/evaluation/samples/inv_01_digital_standard.pdf)).
   - Observe upload progress bar $\rightarrow$ automatic redirection to the Review screen.
   - Verify extracted fields: Vendor name ("Acme Industrial Supplies"), Invoice Number ("INV-2026-101"), Dates, Currency, and Line Items.
3. **Side-by-Side Source Preview**:
   - Inspect the embedded original PDF document viewer on the left side of the Review screen.
4. **Validation Findings & Reconciliation**:
   - Upload an invoice with arithmetic errors (e.g. [`inv_05_digital_inconsistent.pdf`](file:///c:/Users/MR.%20JEET/Downloads/Invoice_IQ-main/backend/evaluation/samples/inv_05_digital_inconsistent.pdf)).
   - Observe the **Validation findings** callout: *"Identified invoice amounts do not reconcile; review is required"* and the **Needs Review** status badge.
5. **Human Correction & Persistence**:
   - Edit the Vendor Name or adjust a Line Item amount in the form.
   - Click **Save corrections** $\rightarrow$ toast notification confirms save.
   - **Reload the browser page** $\rightarrow$ verify that corrections persist from the SQLite database.
6. **Approval & Review**:
   - Click **Approve invoice** $\rightarrow$ review status updates to **Reviewed**.
7. **Register & Data Export**:
   - Return to the **Invoice register** (`/invoices`) $\rightarrow$ verify the invoice appears in the sortable table.
   - Click **Export register** or export as **JSON** / **CSV** from the review screen $\rightarrow$ observe downloaded structured file.
8. **Negative Test Handling**:
   - Try uploading a `.txt` file or an empty file $\rightarrow$ observe immediate rejection with a descriptive error message.

---

## 9. Academic Report Material

A structured project-report draft based on the implemented system and verified evaluation results is available at [docs/InvoiceIQ_Project_Report_Material.md](docs/InvoiceIQ_Project_Report_Material.md).

## 10. Known Limitations

- **Host Runtime OCR Compatibility**: On Windows environments running Python 3.14, `onnxruntime` native C++ extensions experience access violations during image OCR. An isolated capability probe prevents server crashes and falls back to empty text for manual review. Full raster image OCR is recommended to run on Python 3.11/3.12 or within a Linux container.
- **Unconventional Table Layouts**: Line items without standard separators (`|` or consistent whitespace columns) or with multi-line wrapped descriptions will leave line items empty for manual entry.
- **Token Confidence Alignment**: RapidOCR produces token-level confidences, but token-to-field alignment is heuristic.
