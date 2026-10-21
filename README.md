# InvoiceIQ Frontend

InvoiceIQ is a React + Vite interface for invoice intake, human-in-the-loop review, validation, and structured exports.

## Run locally

```bash
npm install
cp .env.example .env
npm run dev
```

For a production build:

```bash
npm run build
npm run preview
```

## Environment configuration

```env
VITE_API_MODE=mock
VITE_API_BASE_URL=http://localhost:8000
VITE_MAX_UPLOAD_MB=10
```

- `mock` is the default local workspace mode and uses in-memory records. Uploaded files are **not** analyzed by OCR or AI in this mode, and records reset on page reload.
- `live` uses the configured FastAPI backend. Network/API failures are shown to the user; the application does not silently fall back to local records.
- Never place private API keys or secrets in frontend environment variables.

## Main features

- Responsive SaaS workspace with overview, invoice register, upload, review, and settings pages.
- Light/dark theme toggle with saved preference.
- Global quick search (`Ctrl/Cmd + K`) across invoices and vendors.
- Functional notifications for invoices awaiting review or processing attention.
- Filters for review status, processing status, and invoice date range.
- Sortable invoice table and summary metrics.
- PDF/image upload validation and upload progress in live mode.
- Invoice, vendor, customer, financial-summary, and line-item editing.
- Backend-provided confidence indicators and validation warnings.
- CSV/JSON export from the review screen and CSV export for the filtered register.
- Account profile and workspace preferences saved locally in the browser.
- Local/API connection status in Settings.

## Architecture

- `src/pages/` contains routed screens.
- `src/components/` contains reusable UI components and invoice table.
- `src/services/invoiceApi.js` is the API boundary and owns endpoint paths.
- `src/services/mappers.js` normalizes backend responses for the UI.
- `src/services/localInvoiceApi.js` supplies local workspace records without claiming AI processing.
- `src/utils.js` contains formatting, upload validation, and exports.

## Backend contract to confirm

- `GET /health`
- `GET /invoices`
- `GET /invoices/{id}`
- `POST /invoices/upload` with multipart field `file`
- `PATCH /invoices/{id}`
- `POST /invoices/{id}/review` with `{ "status": "reviewed" }` (or another supported status)

The backend should return stable invoice IDs, processing/review statuses, structured line items, validation warnings, and an `originalFileUrl` if the source document should be previewed in live mode.

## Known limitations

- OCR/AI extraction is a backend responsibility; local workspace mode does not perform extraction.
- Profile details and preferences are browser-local; server-side authentication and account management require backend support.
- No delete or reprocess endpoint is defined in the current API contract, so those actions are not exposed.
- PDF preview uses the browser's built-in viewer; image zoom is available.
- Automated tests should be added before production deployment.
- Production readiness still requires backend integration testing, authentication/authorization, secure file handling, audit logging, and deployment configuration.
