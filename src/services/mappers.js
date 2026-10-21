// Explicit mapping of backend responses -> frontend model. Update ONLY here when the contract changes.
// Processing status and review status are separate properties on purpose.
export const PROCESSING={uploaded:'Uploaded',processing:'Processing',completed:'Completed',failed:'Failed'}
export const REVIEW={pending:'Pending',needs_review:'Needs Review',reviewed:'Reviewed',rejected:'Rejected'}
const alias={queued:'uploaded',pending:'uploaded',running:'processing',done:'completed',success:'completed',error:'failed'}
export function mapInvoice(r){
  if(!r||typeof r!=='object'||!(r.id??r.invoice_id)) throw new Error('Malformed invoice response from server.')
  const g=(a,b)=>r[a]??r[b]??null
  const ps=String(g('processingStatus','processing_status')||'uploaded').toLowerCase()
  const rs=g('reviewStatus','review_status')
  return {...r,id:String(r.id??r.invoice_id),invoiceNumber:g('invoiceNumber','invoice_number'),
    vendor:{name:'',address:'',taxId:'',...(r.vendor||{})},customer:{name:'',address:'',taxId:'',...(r.customer||{})},
    invoiceDate:g('invoiceDate','invoice_date'),dueDate:g('dueDate','due_date'),currency:r.currency||'INR',
    paymentTerms:g('paymentTerms','payment_terms'),subtotal:r.subtotal??null,taxAmount:g('taxAmount','tax_amount'),
    discount:r.discount??null,totalAmount:g('totalAmount','total_amount'),
    lineItems:(r.lineItems||r.line_items||[]).map((l,i)=>({id:l.id||`line-${i}`,description:l.description??'',quantity:l.quantity??null,unitPrice:l.unitPrice??l.unit_price??null,taxRate:l.taxRate??l.tax_rate??null,total:l.total??null})),
    processingStatus:PROCESSING[alias[ps]||ps]?(alias[ps]||ps):'uploaded',
    reviewStatus:REVIEW[rs]?rs:'pending',
    confidence:r.confidence||{},validationWarnings:g('validationWarnings','validation_warnings')||[],
    createdAt:g('createdAt','created_at'),updatedAt:g('updatedAt','updated_at'),originalFileUrl:g('originalFileUrl','original_file_url')}
}
