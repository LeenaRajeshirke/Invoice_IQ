import test from 'node:test'
import assert from 'node:assert/strict'
import { mapInvoice, mapInvoiceUpdate, PROCESSING, REVIEW } from './mappers.js'

test('mapInvoice converts backend snake_case record to frontend camelCase model', () => {
  const backendInvoice = {
    id: 42,
    invoice_number: 'INV-2026-001',
    vendor_name: 'Acme Corporation',
    vendor_address: '100 Industrial Parkway',
    vendor_tax_id: 'US-TAX-123',
    customer_name: 'Globex Corp',
    customer_address: '200 Market Street',
    customer_tax_id: 'US-TAX-456',
    invoice_date: '2026-10-15',
    due_date: '2026-11-15',
    currency: 'USD',
    payment_terms: 'Net 30',
    subtotal: '250.00',
    tax_amount: '20.00',
    discount_amount: '10.00',
    total_amount: '260.00',
    amount_paid: '50.00',
    balance_due: '210.00',
    line_items: [
      {
        description: 'Software License',
        quantity: '2',
        unit_price: '125.00',
        tax_rate: '8.00',
        tax_amount: '20.00',
        total_amount: '250.00',
      },
    ],
    processing_status: 'processed',
    review_status: 'needs_review',
    status: 'uploaded',
    validation_warnings: [
      'Identified invoice amounts do not reconcile; review is required.',
      { field: 'invoice_date', code: 'ambiguous_date', severity: 'warning', message: 'Check date format' },
    ],
    created_at: '2026-10-15T10:00:00Z',
    updated_at: '2026-10-15T10:00:00Z',
    original_file_url: '/invoices/42/file',
  }

  const result = mapInvoice(backendInvoice)

  assert.equal(result.id, '42')
  assert.equal(result.invoiceNumber, 'INV-2026-001')
  assert.deepEqual(result.vendor, {
    name: 'Acme Corporation',
    address: '100 Industrial Parkway',
    taxId: 'US-TAX-123',
  })
  assert.deepEqual(result.customer, {
    name: 'Globex Corp',
    address: '200 Market Street',
    taxId: 'US-TAX-456',
  })
  assert.equal(result.invoiceDate, '2026-10-15')
  assert.equal(result.dueDate, '2026-11-15')
  assert.equal(result.currency, 'USD')
  assert.equal(result.paymentTerms, 'Net 30')
  assert.equal(result.subtotal, '250.00')
  assert.equal(result.taxAmount, '20.00')
  assert.equal(result.discount, '10.00')
  assert.equal(result.totalAmount, '260.00')
  assert.equal(result.amountPaid, '50.00')
  assert.equal(result.balanceDue, '210.00')

  assert.equal(result.lineItems.length, 1)
  assert.equal(result.lineItems[0].description, 'Software License')
  assert.equal(result.lineItems[0].quantity, '2')
  assert.equal(result.lineItems[0].unitPrice, '125.00')
  assert.equal(result.lineItems[0].taxRate, '8.00')
  assert.equal(result.lineItems[0].total, '250.00')

  // Status mapping
  assert.equal(result.processingStatus, 'completed')
  assert.equal(result.reviewStatus, 'needs_review')

  // Validation warnings normalized
  assert.equal(result.validationWarnings.length, 2)
  assert.equal(result.validationWarnings[0].message, 'Identified invoice amounts do not reconcile; review is required.')
  assert.equal(result.validationWarnings[0].severity, 'warning')
  assert.equal(result.validationWarnings[1].field, 'invoice_date')
  assert.equal(result.validationWarnings[1].message, 'Check date format')

  assert.equal(result.originalFileUrl, '/invoices/42/file')
})

test('mapInvoice handles upload response with invoice_id and alias statuses', () => {
  const uploadResponse = {
    invoice_id: 99,
    processing_status: 'placeholder',
    review_status: 'pending',
  }

  const mapped = mapInvoice(uploadResponse)
  assert.equal(mapped.id, '99')
  assert.equal(mapped.processingStatus, 'uploaded')
  assert.equal(mapped.reviewStatus, 'pending')
})

test('mapInvoice throws on invalid or empty record', () => {
  assert.throws(() => mapInvoice(null), /Malformed invoice response/)
  assert.throws(() => mapInvoice({}), /Malformed invoice response/)
})

test('mapInvoiceUpdate converts frontend camelCase model to backend snake_case payload', () => {
  const frontendInvoice = {
    id: '42',
    invoiceNumber: 'INV-UPDATED',
    vendor: {
      name: 'Acme Updated Ltd',
      address: '789 Main St',
      taxId: 'TAX-789',
    },
    customer: {
      name: 'Customer LLC',
      address: '456 Elm St',
      taxId: 'TAX-456',
    },
    invoiceDate: '2026-10-20',
    dueDate: '2026-11-20',
    currency: 'USD',
    paymentTerms: 'Net 15',
    subtotal: 100,
    taxAmount: 8,
    discount: 5,
    totalAmount: 103,
    amountPaid: 0,
    balanceDue: 103,
    lineItems: [
      {
        description: 'New service',
        quantity: 1,
        unitPrice: 100,
        taxRate: 8,
        taxAmount: 8,
        total: 108,
      },
    ],
  }

  const payload = mapInvoiceUpdate(frontendInvoice)

  assert.equal(payload.invoice_number, 'INV-UPDATED')
  assert.equal(payload.vendor_name, 'Acme Updated Ltd')
  assert.equal(payload.vendor_address, '789 Main St')
  assert.equal(payload.vendor_tax_id, 'TAX-789')
  assert.equal(payload.customer_name, 'Customer LLC')
  assert.equal(payload.customer_address, '456 Elm St')
  assert.equal(payload.customer_tax_id, 'TAX-456')
  assert.equal(payload.invoice_date, '2026-10-20')
  assert.equal(payload.due_date, '2026-11-20')
  assert.equal(payload.currency, 'USD')
  assert.equal(payload.payment_terms, 'Net 15')
  assert.equal(payload.subtotal, 100)
  assert.equal(payload.tax_amount, 8)
  assert.equal(payload.discount_amount, 5)
  assert.equal(payload.total_amount, 103)
  assert.equal(payload.amount_paid, 0)
  assert.equal(payload.balance_due, 103)

  assert.equal(payload.line_items.length, 1)
  assert.equal(payload.line_items[0].description, 'New service')
  assert.equal(payload.line_items[0].quantity, 1)
  assert.equal(payload.line_items[0].unit_price, 100)
  assert.equal(payload.line_items[0].total_amount, 108)
})
