import axios from 'axios'
import { config } from '../config'
import { createLiveApi } from './apiClient'
import { localApi } from './localInvoiceApi'

const http = axios.create({ baseURL: config.baseUrl, timeout: 30000 })

export function errMsg(error) {
  if (error?.code === 'ECONNABORTED') {
    return 'The request timed out. Check that the backend is running and try again.'
  }
  if (error?.request && !error?.response) {
    return `Cannot reach the backend at ${config.baseUrl}. Is FastAPI running?`
  }

  const detail = error?.response?.data?.detail
  if (error?.response) {
    const message = typeof detail === 'string'
      ? detail
      : Array.isArray(detail)
        ? detail.map(item => {
          const field = Array.isArray(item.loc) ? item.loc.slice(1).join('.') : ''
          return `${field ? `${field}: ` : ''}${item.msg || 'Invalid value'}`
        }).join('; ')
        : detail?.message || ''
    return `Server error ${error.response.status}${message ? `: ${message}` : ''}`
  }
  return error?.message || 'Unexpected error.'
}

export const invoiceApi = config.mode === 'live' ? createLiveApi(http) : localApi
