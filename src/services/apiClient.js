import { mapInvoice, mapInvoiceUpdate } from './mappers.js'

const encode = value => encodeURIComponent(value)

export function createLiveApi(http) {
  return {
    health: () => http.get('/health').then(response => response.data),

    list: () => http.get('/invoices').then(response => {
      const records = Array.isArray(response.data) ? response.data : response.data?.items
      if (!Array.isArray(records)) throw new Error('Malformed invoice list response.')
      return records.map(mapInvoice)
    }),

    get: id => http.get(`/invoices/${encode(id)}`).then(response => mapInvoice(response.data)),

    getFile: (id, fileUrl) => {
      if (!fileUrl) return Promise.resolve(null)
      return http.get(`/invoices/${encode(id)}/file`, { responseType: 'blob' }).then(response => response.data)
    },

    upload: async (file, onProgress) => {
      const form = new FormData()
      form.append('file', file)
      const response = await http.post('/invoices/upload', form, {
        onUploadProgress: event => {
          if (event.total) onProgress?.(Math.round((event.loaded * 100) / event.total))
        },
      })
      const id = response.data?.invoice_id ?? response.data?.id
      if (id == null) throw new Error('Malformed invoice upload response.')
      const invoiceResponse = await http.get(`/invoices/${encode(id)}`)
      return {
        ...mapInvoice(invoiceResponse.data),
        uploadCount: response.data?.invoice_count ?? 1,
        processingMessage: response.data?.message ?? '',
      }
    },

    retry: async id => {
      const result = await http.post(`/invoices/${encode(id)}/retry`)
      const invoice = await http.get(`/invoices/${encode(id)}`)
      return {
        ...mapInvoice(invoice.data),
        processingMessage: result.data?.message ?? '',
      }
    },

    save: (id, invoice) => http.patch(
      `/invoices/${encode(id)}`,
      mapInvoiceUpdate(invoice),
    ).then(response => mapInvoice(response.data)),

    setReview: (id, status) => http.post(
      `/invoices/${encode(id)}/review`,
      { status },
    ).then(response => mapInvoice(response.data)),
  }
}
