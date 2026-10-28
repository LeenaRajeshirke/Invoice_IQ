import test from 'node:test'
import assert from 'node:assert/strict'
import { createLiveApi } from './apiClient.js'

test('createLiveApi - health calls GET /health', async () => {
  const http = {
    get: async url => {
      assert.equal(url, '/health')
      return { data: { status: 'ok' } }
    },
  }
  const api = createLiveApi(http)
  const result = await api.health()
  assert.deepEqual(result, { status: 'ok' })
})

test('createLiveApi - list calls GET /invoices and maps records', async () => {
  const http = {
    get: async url => {
      assert.equal(url, '/invoices')
      return {
        data: [
          { id: 1, invoice_number: 'INV-1', vendor_name: 'V1', total_amount: '100.00' },
          { id: 2, invoice_number: 'INV-2', vendor_name: 'V2', total_amount: '200.00' },
        ],
      }
    },
  }
  const api = createLiveApi(http)
  const items = await api.list()
  assert.equal(items.length, 2)
  assert.equal(items[0].id, '1')
  assert.equal(items[0].invoiceNumber, 'INV-1')
  assert.equal(items[0].vendor.name, 'V1')
  assert.equal(items[1].id, '2')
})

test('createLiveApi - get calls GET /invoices/{id} and maps record', async () => {
  const http = {
    get: async url => {
      assert.equal(url, '/invoices/10')
      return {
        data: { id: 10, invoice_number: 'INV-10', vendor_name: 'Vendor Ten', total_amount: '500.00' },
      }
    },
  }
  const api = createLiveApi(http)
  const invoice = await api.get('10')
  assert.equal(invoice.id, '10')
  assert.equal(invoice.invoiceNumber, 'INV-10')
  assert.equal(invoice.vendor.name, 'Vendor Ten')
})

test('createLiveApi - upload posts multipart file and retrieves created invoice', async () => {
  const calls = []
  const http = {
    post: async (url, formData) => {
      calls.push({ method: 'POST', url, formData })
      return { data: { invoice_id: 15, processing_status: 'processed', invoice_count: 2, message: 'Workflow complete.' } }
    },
    get: async url => {
      calls.push({ method: 'GET', url })
      return { data: { id: 15, invoice_number: 'INV-NEW', vendor_name: 'New Vendor' } }
    },
  }
  const api = createLiveApi(http)
  const fakeFile = new Blob(['%PDF-1.7...'], { type: 'application/pdf' })
  fakeFile.name = 'sample.pdf'

  const record = await api.upload(fakeFile)

  assert.equal(calls.length, 2)
  assert.equal(calls[0].url, '/invoices/upload')
  assert.equal(calls[1].url, '/invoices/15')
  assert.equal(record.id, '15')
  assert.equal(record.invoiceNumber, 'INV-NEW')
  assert.equal(record.vendor.name, 'New Vendor')
  assert.equal(record.uploadCount, 2)
  assert.equal(record.processingMessage, 'Workflow complete.')
})

test('createLiveApi - save sends PATCH /invoices/{id} with mapped payload', async () => {
  let patchPayload = null
  const http = {
    patch: async (url, payload) => {
      assert.equal(url, '/invoices/15')
      patchPayload = payload
      return {
        data: {
          id: 15,
          invoice_number: payload.invoice_number,
          vendor_name: payload.vendor_name,
        },
      }
    },
  }
  const api = createLiveApi(http)
  const updated = await api.save('15', {
    invoiceNumber: 'INV-EDITED',
    vendor: { name: 'Edited Vendor' },
  })

  assert.equal(patchPayload.invoice_number, 'INV-EDITED')
  assert.equal(patchPayload.vendor_name, 'Edited Vendor')
  assert.equal(updated.invoiceNumber, 'INV-EDITED')
  assert.equal(updated.vendor.name, 'Edited Vendor')
})

test('createLiveApi - setReview sends POST /invoices/{id}/review', async () => {
  let reviewPayload = null
  const http = {
    post: async (url, payload) => {
      assert.equal(url, '/invoices/15/review')
      reviewPayload = payload
      return { data: { id: 15, review_status: payload.status } }
    },
  }
  const api = createLiveApi(http)
  const reviewed = await api.setReview('15', 'reviewed')
  assert.deepEqual(reviewPayload, { status: 'reviewed' })
  assert.equal(reviewed.reviewStatus, 'reviewed')
})

test('createLiveApi - retry reuses invoice record and exposes processing message', async () => {
  const calls = []
  const http = {
    post: async url => {
      calls.push(url)
      return { data: { message: 'Retry complete.' } }
    },
    get: async url => {
      calls.push(url)
      return { data: { id: 21, processing_status: 'processed' } }
    },
  }
  const api = createLiveApi(http)
  const invoice = await api.retry(21)
  assert.deepEqual(calls, ['/invoices/21/retry', '/invoices/21'])
  assert.equal(invoice.id, '21')
  assert.equal(invoice.processingStatus, 'completed')
  assert.equal(invoice.processingMessage, 'Retry complete.')
})

test('createLiveApi - getFile fetches blob from /invoices/{id}/file', async () => {
  const fakeBlob = new Blob(['bytes'])
  const http = {
    get: async (url, options) => {
      assert.equal(url, '/invoices/15/file')
      assert.equal(options.responseType, 'blob')
      return { data: fakeBlob }
    },
  }
  const api = createLiveApi(http)
  const file = await api.getFile('15', '/invoices/15/file')
  assert.equal(file, fakeBlob)
})
