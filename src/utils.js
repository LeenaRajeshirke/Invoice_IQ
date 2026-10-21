import { config } from './config'

export const money = (value, currency = 'INR') => {
  if (value == null || value === '') return '—'
  const amount = Number(value)
  if (!Number.isFinite(amount)) return '—'
  try { return new Intl.NumberFormat('en-IN', { style: 'currency', currency: currency || 'INR', maximumFractionDigits: 2 }).format(amount) }
  catch { return new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 }).format(amount) }
}
export const fmtDate = value => { if (!value) return '—'; const date = new Date(value); return Number.isNaN(date.getTime()) ? '—' : date.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) }
export const confPct = value => value == null || value === '' || Number.isNaN(Number(value)) ? null : Math.round(Number(value) <= 1 ? Number(value) * 100 : Number(value))
export const confLevel = pct => pct == null ? 'na' : pct >= config.high ? 'high' : pct >= config.mid ? 'mid' : 'low'
const ALLOWED = { pdf: ['application/pdf'], png: ['image/png'], jpg: ['image/jpeg'], jpeg: ['image/jpeg'] }
export function validateFile(file) {
  if (!file?.name) return 'Choose a file to upload.'
  const ext = file.name.split('.').pop().toLowerCase()
  if (!ALLOWED[ext]) return 'Unsupported file type. Use PDF, PNG, JPG or JPEG.'
  if (file.type && !ALLOWED[ext].includes(file.type)) return 'File content type does not match its extension.'
  if (file.size > config.maxMB * 1024 * 1024) return `File is too large. Maximum size is ${config.maxMB} MB.`
  if (file.size === 0) return 'File is empty.'
  return null
}
export const sizeStr = bytes => bytes >= 1048576 ? `${(bytes / 1048576).toFixed(2)} MB` : `${(bytes / 1024).toFixed(1)} KB`
export function download(name, content, type) {
  const url = URL.createObjectURL(new Blob([content], { type }))
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = name; document.body.appendChild(anchor); anchor.click(); anchor.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}
const esc = value => { const s = value == null ? '' : String(value); return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s }
export function toCsv(invoice) {
  const headers = ['invoice_number', 'vendor', 'vendor_tax_id', 'vendor_address', 'customer', 'customer_tax_id', 'customer_address', 'invoice_date', 'due_date', 'currency', 'payment_terms', 'subtotal', 'tax', 'discount', 'amount_paid', 'balance_due', 'total', 'processing_status', 'review_status', 'line_description', 'quantity', 'unit_price', 'tax_rate', 'line_total']
  const lines = Array.isArray(invoice.lineItems) ? invoice.lineItems : []
  const rows = (lines.length ? lines : [{}]).map(line => [invoice.invoiceNumber, invoice.vendor?.name, invoice.vendor?.taxId, invoice.vendor?.address, invoice.customer?.name, invoice.customer?.taxId, invoice.customer?.address, invoice.invoiceDate, invoice.dueDate, invoice.currency, invoice.paymentTerms, invoice.subtotal, invoice.taxAmount, invoice.discount, invoice.amountPaid ?? invoice.amount_paid, invoice.balanceDue ?? invoice.balance_due, invoice.totalAmount, invoice.processingStatus, invoice.reviewStatus, line.description, line.quantity, line.unitPrice ?? line.unit_price, line.taxRate ?? line.tax_rate, line.total])
  return '\uFEFF' + [headers, ...rows].map(row => row.map(esc).join(',')).join('\r\n')
}
export const toJson = invoice => JSON.stringify({ ...invoice, vendor: invoice.vendor || {}, customer: invoice.customer || {}, lineItems: invoice.lineItems || [], validationWarnings: invoice.validationWarnings || [] }, null, 2)
