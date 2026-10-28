import { useEffect, useMemo, useRef, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import toast from 'react-hot-toast'
import { Plus, Trash2, Save, Download, ZoomIn, ZoomOut, ExternalLink, ArrowLeft, FileText, Info, CheckCircle2, Clock3 } from 'lucide-react'
import { invoiceApi, errMsg } from '../services/invoiceApi'
import { Spinner, ErrorState, StatusBadge, ConfidenceBadge, Warning, ConfirmDialog, PageHeader } from '../components/common'
import { download, toCsv, toJson, money } from '../utils'

const setPath = (o, p, v) => { const c = structuredClone(o); let target = c; const keys = p.split('.'); keys.slice(0, -1).forEach(k => { target[k] = target[k] ?? {}; target = target[k] }); target[keys.at(-1)] = v; return c }
const num = v => v === '' ? null : Number(v)

function ReviewField({ form, edit, label, path, type = 'text', conf, placeholder }) {
  const value = path.split('.').reduce((o, k) => o?.[k], form)
  return <label className="block min-w-0"><span className="field-label flex items-center justify-between gap-2">{label}{conf && <ConfidenceBadge value={form.confidence?.[conf]}/>}</span><input className="inp" type={type} step={type === 'number' ? '0.01' : undefined} value={value ?? ''} placeholder={placeholder || ''} onChange={e => edit(path, type === 'number' ? num(e.target.value) : e.target.value || null)}/></label>
}
function ReviewSection({ title, children }) { return <fieldset className="panel review-section"><legend>{title}</legend><div className="section-grid">{children}</div></fieldset> }

function Preview({ id, url }) {
  const [zoom, setZoom] = useState(1), [failed, setFailed] = useState(false), [loading, setLoading] = useState(Boolean(url))
  const [obj, setObj] = useState(null)
  useEffect(() => {
    let active = true
    let objectUrl
    setFailed(false)
    setObj(null)
    setLoading(Boolean(url))
    Promise.resolve(invoiceApi.getFile?.(id, url)).then(file => {
      if (!active) return
      if (!file) { setLoading(false); return }
      objectUrl = URL.createObjectURL(file)
      setObj({ u: objectUrl, type: file.type })
      setLoading(false)
    }).catch(() => {
      if (active) { setFailed(true); setLoading(false) }
    })
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [id, url])
  const src = obj?.u, isPdf = obj?.type === 'application/pdf'
  return <section className="panel"><div className="panel-title-row"><div><h2 className="panel-title">Original document</h2><p className="panel-subtitle">Compare the source with the extracted values.</p></div><div className="flex gap-1"><button className="icon-button" aria-label="Zoom out" title="Zoom out" disabled={zoom <= .5 || isPdf} onClick={() => setZoom(z => z - .25)}><ZoomOut size={15}/></button><button className="icon-button" aria-label="Zoom in" title="Zoom in" disabled={zoom >= 3 || isPdf} onClick={() => setZoom(z => z + .25)}><ZoomIn size={15}/></button>{src && <a className="icon-button" href={src} target="_blank" rel="noreferrer" aria-label="Open original document" title="Open original document"><ExternalLink size={15}/></a>}</div></div>
    <div className="preview-frame">{loading ? <div className="empty-state self-center"><FileText size={32} className="mx-auto"/><h3>Loading original document</h3></div> : !src || failed ? <div className="empty-state self-center"><FileText size={32} className="mx-auto"/><h3>{failed ? 'Preview unavailable' : 'No original file attached'}</h3><p>{failed ? 'This file could not be loaded from the backend.' : 'A source preview will appear here when the original document is available.'}</p></div> : isPdf ? <iframe title="Invoice PDF preview" src={src} className="w-full h-full border-0" onError={() => setFailed(true)}/> : <img alt="Uploaded invoice" src={src} style={{ width: `${zoom * 100}%`, maxWidth: 'none', height: 'auto' }} onError={() => setFailed(true)}/>}</div>
    <div className="flex items-center gap-2 mt-3 tiny-label"><Info size={13}/>{isPdf ? 'PDF preview uses the browser viewer.' : `Image zoom · ${Math.round(zoom * 100)}%`}</div>
  </section>
}

export default function Review() {
  const { id } = useParams()
  const [saved, setSaved] = useState(null), [form, setForm] = useState(null), [error, setError] = useState(null), [busy, setBusy] = useState(false), [confirm, setConfirm] = useState(false)
  const saving = useRef(false)
  useEffect(() => { let active = true; setSaved(null); setForm(null); setError(null); invoiceApi.get(id).then(i => { if (active) { setSaved(i); setForm(structuredClone(i)) } }).catch(e => active && setError(errMsg(e))); return () => { active = false } }, [id])
  const dirty = saved && form && JSON.stringify(saved) !== JSON.stringify(form)
  useEffect(() => { if (!dirty) return; const handler = e => { e.preventDefault(); e.returnValue = '' }; window.addEventListener('beforeunload', handler); return () => window.removeEventListener('beforeunload', handler) }, [dirty])
  if (error) return <ErrorState message={error}/>
  if (!form) return <Spinner label="Opening invoice review…"/>

  const edit = (path, value) => setForm(f => setPath(f, path, value))
  const editLine = (index, key, value) => setForm(f => ({ ...f, lineItems: f.lineItems.map((line, i) => i === index ? { ...line, [key]: value } : line) }))
  const run = async (fn, message) => { if (saving.current) return; saving.current = true; setBusy(true); try { const result = await fn(); setSaved(result); setForm(structuredClone(result)); toast.success(message) } catch (e) { toast.error(`${errMsg(e)} Your edits were kept.`) } finally { saving.current = false; setBusy(false) } }
  const payload = () => { const { id: _id, ...rest } = form; return rest }
  const save = () => run(() => invoiceApi.save(id, payload()), 'Corrections saved.')
  const review = status => run(async () => { if (dirty) await invoiceApi.save(id, payload()); return invoiceApi.setReview(id, status) }, 'Review status updated.')
  const doExport = kind => { try { kind === 'json' ? download(`${form.invoiceNumber || form.id}.json`, toJson(form), 'application/json') : download(`${form.invoiceNumber || form.id}.csv`, toCsv(form), 'text/csv;charset=utf-8'); toast.success('Export generated.') } catch { toast.error('Export could not be generated.') } }
  const warningCount = form.validationWarnings?.length || 0
  return <>
    <PageHeader title={form.invoiceNumber || 'Invoice review'} subtitle="Verify the source document, correct uncertain fields, and confirm the review status." eyebrow="HUMAN-IN-THE-LOOP REVIEW">
      <Link to="/invoices" className="btn"><ArrowLeft size={14}/>Back to register</Link><button className="btn" onClick={() => doExport('json')}><Download size={14}/>JSON</button><button className="btn" onClick={() => doExport('csv')}><Download size={14}/>CSV</button>
    </PageHeader>
    <div className="flex items-center gap-2 flex-wrap mb-4"><StatusBadge value={form.processingStatus}/><StatusBadge kind="review" value={saved.reviewStatus}/>{dirty && <span className="status-badge badge-amber"><Clock3 size={11}/>Unsaved changes</span>}</div>
    <div className="review-layout"><div className="review-sticky"><Preview id={id} url={form.originalFileUrl}/></div><div>
      {warningCount > 0 && <section className="panel mb-3"><div className="panel-title-row"><div><h2 className="panel-title">Validation findings</h2><p className="panel-subtitle">{warningCount} item{warningCount === 1 ? '' : 's'} reported by the data service.</p></div><span className="status-badge badge-amber">Needs attention</span></div><ul className="warning-list">{form.validationWarnings.map((w, i) => <Warning key={`${w.field || 'warning'}-${i}`} w={w}/>)}</ul></section>}
      <ReviewSection title="Invoice details"><ReviewField form={form} edit={edit} label="Invoice number" path="invoiceNumber" conf="invoiceNumber" placeholder="e.g. INV-1001"/><ReviewField form={form} edit={edit} label="Currency" path="currency" conf="currency" placeholder="INR"/><ReviewField form={form} edit={edit} label="Invoice date" path="invoiceDate" type="date" conf="invoiceDate"/><ReviewField form={form} edit={edit} label="Due date" path="dueDate" type="date" conf="dueDate"/><ReviewField form={form} edit={edit} label="Payment terms" path="paymentTerms" placeholder="e.g. Net 30"/></ReviewSection>
      <ReviewSection title="Vendor information"><ReviewField form={form} edit={edit} label="Vendor name" path="vendor.name" conf="vendor"/><ReviewField form={form} edit={edit} label="Vendor tax ID" path="vendor.taxId" placeholder="GSTIN / tax identifier"/><div className="span-two"><ReviewField form={form} edit={edit} label="Vendor address" path="vendor.address"/></div></ReviewSection>
      <ReviewSection title="Customer information"><ReviewField form={form} edit={edit} label="Customer name" path="customer.name"/><ReviewField form={form} edit={edit} label="Customer tax ID" path="customer.taxId"/><div className="span-two"><ReviewField form={form} edit={edit} label="Customer address" path="customer.address"/></div></ReviewSection>
      <ReviewSection title="Financial summary"><ReviewField form={form} edit={edit} label="Subtotal" path="subtotal" type="number" conf="subtotal"/><ReviewField form={form} edit={edit} label="Tax amount" path="taxAmount" type="number" conf="taxAmount"/><ReviewField form={form} edit={edit} label="Discount" path="discount" type="number"/><ReviewField form={form} edit={edit} label="Total amount" path="totalAmount" type="number" conf="totalAmount"/><ReviewField form={form} edit={edit} label="Amount paid" path="amountPaid" type="number"/><ReviewField form={form} edit={edit} label="Balance due" path="balanceDue" type="number"/></ReviewSection>
      <section className="panel mb-3"><div className="panel-title-row"><div><h2 className="panel-title">Line items</h2><p className="panel-subtitle">Review quantities, unit prices, tax rates, and line totals.</p></div><button className="btn btn-soft" onClick={() => setForm(f => ({ ...f, lineItems: [...(f.lineItems || []), { id: `new-${Date.now()}`, description: '', quantity: null, unitPrice: null, taxRate: null, total: null }] }))}><Plus size={14}/>Add item</button></div>
        {!form.lineItems?.length ? <div className="empty-state"><FileText size={25} className="mx-auto"/><h3>No line items extracted</h3><p>Add an item manually if this invoice includes one.</p></div> : <div className="table-wrap"><table className="invoice-table line-table"><thead><tr><th>Description</th><th>Qty</th><th>Unit price</th><th>Tax %</th><th>Line total</th><th/></tr></thead><tbody>{form.lineItems.map((line, index) => <tr key={line.id || index}><td><input aria-label="Line description" className="inp" value={line.description ?? ''} onChange={e => editLine(index, 'description', e.target.value)}/></td>{['quantity', 'unitPrice', 'taxRate', 'total'].map(key => <td key={key}><input aria-label={key} type="number" step="0.01" className="inp" style={{ minWidth: 80 }} value={line[key] ?? ''} onChange={e => editLine(index, key, num(e.target.value))}/></td>)}<td><button className="icon-button" aria-label="Remove line item" onClick={() => setForm(f => ({ ...f, lineItems: f.lineItems.filter((_, i) => i !== index) }))}><Trash2 size={15}/></button></td></tr>)}</tbody></table></div>}
        <div className="flex justify-end mt-3 pt-3 border-t border-slate-100"><b className="text-sm">Invoice total: {money(form.totalAmount, form.currency)}</b></div>
      </section>
      <div className="review-actions"><button className="btn btn-p" disabled={!dirty || busy} onClick={save}><Save size={14}/>{busy ? 'Saving…' : 'Save corrections'}</button><button className="btn" disabled={busy} onClick={() => review('reviewed')}><CheckCircle2 size={14}/>Approve invoice</button><button className="btn" disabled={busy} onClick={() => review('needs_review')}>Needs review</button><button className="btn btn-danger" disabled={busy} onClick={() => setConfirm(true)}>Reject</button></div>
    </div></div>
    <ConfirmDialog open={confirm} title="Reject this invoice?" text="The invoice status will be changed to Rejected. You can update the status later." onNo={() => setConfirm(false)} onYes={() => { setConfirm(false); review('rejected') }}/>
  </>
}
