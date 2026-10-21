import { useEffect, useState, useCallback } from 'react'
import { invoiceApi, errMsg } from './services/invoiceApi'
// Loads the invoice list once; exposes reload. Errors are surfaced, never swallowed.
export function useInvoices(){
  const [data,setData]=useState(null),[error,setError]=useState(null)
  const load=useCallback(()=>{setError(null);setData(null);invoiceApi.list().then(setData).catch(e=>setError(errMsg(e)))},[])
  useEffect(()=>{load()},[load])
  return {invoices:data,error,reload:load}
}
