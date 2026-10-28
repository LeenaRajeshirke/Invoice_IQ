// Keep the API's flat snake_case representation separate from the UI model.
export const PROCESSING = {
  uploaded: 'Uploaded',
  processing: 'Processing',
  completed: 'Completed',
  failed: 'Failed',
}

export const REVIEW = {
  pending: 'Pending',
  needs_review: 'Needs Review',
  reviewed: 'Reviewed',
  rejected: 'Rejected',
}

const processingAliases = {
  queued: 'uploaded',
  pending: 'uploaded',
  placeholder: 'uploaded',
  running: 'processing',
  processed: 'completed',
  done: 'completed',
  success: 'completed',
  error: 'failed',
}

const value = (record, camel, snake) => record[camel] ?? record[snake] ?? null

function mapWarning(warning) {
  if (typeof warning === 'string') {
    return { field: null, code: 'legacy_warning', severity: 'warning', message: warning }
  }

  if (!warning || typeof warning !== 'object') {
    return { field: null, code: 'unknown_warning', severity: 'warning', message: String(warning ?? '') }
  }

  return {
    field: warning.field ?? null,
    code: warning.code ?? null,
    severity: warning.severity ?? 'warning',
    message: warning.message ?? warning.detail ?? '',
  }
}

export function mapInvoice(record) {
  if (!record || typeof record !== 'object' || (record.id ?? record.invoice_id) == null) {
    throw new Error('Malformed invoice response from server.')
  }

  const vendor = record.vendor ?? {}
  const customer = record.customer ?? {}
  const rawProcessingStatus = String(
    value(record, 'processingStatus', 'processing_status') ?? record.status ?? 'uploaded',
  ).toLowerCase()
  const processingStatus = processingAliases[rawProcessingStatus] ?? rawProcessingStatus
  const rawReviewStatus = String(value(record, 'reviewStatus', 'review_status') ?? 'pending').toLowerCase()
  const warnings = value(record, 'validationWarnings', 'validation_warnings')

  return {
    ...record,
    id: String(record.id ?? record.invoice_id),
    invoiceNumber: value(record, 'invoiceNumber', 'invoice_number'),
    vendor: {
      name: vendor.name ?? record.vendor_name ?? '',
      address: vendor.address ?? record.vendor_address ?? '',
      taxId: vendor.taxId ?? vendor.tax_id ?? record.vendor_tax_id ?? '',
    },
    customer: {
      name: customer.name ?? record.customer_name ?? '',
      address: customer.address ?? record.customer_address ?? '',
      taxId: customer.taxId ?? customer.tax_id ?? record.customer_tax_id ?? '',
    },
    invoiceDate: value(record, 'invoiceDate', 'invoice_date'),
    dueDate: value(record, 'dueDate', 'due_date'),
    currency: record.currency ?? null,
    paymentTerms: value(record, 'paymentTerms', 'payment_terms'),
    subtotal: record.subtotal ?? null,
    taxAmount: value(record, 'taxAmount', 'tax_amount'),
    discount: record.discount ?? record.discount_amount ?? record.discountAmount ?? null,
    totalAmount: value(record, 'totalAmount', 'total_amount'),
    amountPaid: value(record, 'amountPaid', 'amount_paid'),
    balanceDue: value(record, 'balanceDue', 'balance_due'),
    lineItems: (record.lineItems ?? record.line_items ?? []).map((line, index) => ({
      id: line.id ?? `line-${index}`,
      description: line.description ?? '',
      quantity: line.quantity ?? null,
      unitPrice: line.unitPrice ?? line.unit_price ?? null,
      taxRate: line.taxRate ?? line.tax_rate ?? null,
      taxAmount: line.taxAmount ?? line.tax_amount ?? null,
      total: line.total ?? line.totalAmount ?? line.total_amount ?? null,
    })),
    processingStatus: PROCESSING[processingStatus] ? processingStatus : rawProcessingStatus,
    reviewStatus: REVIEW[rawReviewStatus] ? rawReviewStatus : rawReviewStatus,
    confidence: record.confidence ?? {},
    validationWarnings: Array.isArray(warnings) ? warnings.map(mapWarning) : [],
    createdAt: value(record, 'createdAt', 'created_at'),
    updatedAt: value(record, 'updatedAt', 'updated_at'),
    originalFileUrl: value(record, 'originalFileUrl', 'original_file_url'),
  }
}

export function mapInvoiceUpdate(invoice) {
  return {
    vendor_name: invoice.vendor?.name ?? null,
    vendor_address: invoice.vendor?.address ?? null,
    vendor_tax_id: invoice.vendor?.taxId ?? null,
    customer_name: invoice.customer?.name ?? null,
    customer_address: invoice.customer?.address ?? null,
    customer_tax_id: invoice.customer?.taxId ?? null,
    invoice_number: invoice.invoiceNumber ?? null,
    invoice_date: invoice.invoiceDate ?? null,
    due_date: invoice.dueDate ?? null,
    currency: invoice.currency ?? null,
    payment_terms: invoice.paymentTerms ?? null,
    subtotal: invoice.subtotal ?? null,
    tax_amount: invoice.taxAmount ?? null,
    discount_amount: invoice.discount ?? null,
    total_amount: invoice.totalAmount ?? null,
    amount_paid: invoice.amountPaid ?? null,
    balance_due: invoice.balanceDue ?? null,
    line_items: (invoice.lineItems ?? []).map(line => ({
      description: line.description ?? '',
      quantity: line.quantity ?? null,
      unit_price: line.unitPrice ?? line.unit_price ?? null,
      tax_rate: line.taxRate ?? line.tax_rate ?? null,
      tax_amount: line.taxAmount ?? line.tax_amount ?? null,
      total_amount: line.total ?? line.totalAmount ?? line.total_amount ?? null,
    })),
  }
}
