// Single entry point for the UI. Endpoint paths live ONLY here (to confirm with backend teammate).
// In live mode there is NO silent fallback to mock data: errors propagate to the UI.
import axios from 'axios'
import { config } from '../config'
import { mapInvoice } from './mappers'
import { localApi } from './localInvoiceApi'
const http=axios.create({baseURL:config.baseUrl,timeout:30000})
export function errMsg(e){
  if(e.code==='ECONNABORTED')return 'The request timed out. Check that the backend is running and try again.'
  if(e.request&&!e.response)return `Cannot reach the backend at ${config.baseUrl}. Is FastAPI running?`
  if(e.response){const d=e.response.data?.detail;return `Server error ${e.response.status}${typeof d==='string'?': '+d:''}`}
  return e.message||'Unexpected error.'
}
const enc=encodeURIComponent
const live={
  health:()=>http.get('/health').then(r=>r.data),
  list:()=>http.get('/invoices').then(r=>{const a=Array.isArray(r.data)?r.data:r.data?.items;if(!Array.isArray(a))throw new Error('Malformed invoice list response.');return a.map(mapInvoice)}),
  get:id=>http.get(`/invoices/${enc(id)}`).then(r=>mapInvoice(r.data)),
  getFile:()=>null,
  upload:(file,onProgress)=>{const fd=new FormData();fd.append('file',file)
    return http.post('/invoices/upload',fd,{onUploadProgress:e=>e.total&&onProgress?.(Math.round(e.loaded*100/e.total))}).then(r=>mapInvoice(r.data))},
  save:(id,data)=>http.patch(`/invoices/${enc(id)}`,data).then(r=>mapInvoice(r.data)),
  setReview:(id,status)=>http.post(`/invoices/${enc(id)}/review`,{status}).then(r=>mapInvoice(r.data)),
}
export const invoiceApi=config.mode==='live'?live:localApi
