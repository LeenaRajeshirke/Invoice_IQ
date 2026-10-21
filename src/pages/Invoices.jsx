import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Search, SlidersHorizontal, X, Upload, Download, FileSpreadsheet } from 'lucide-react'
import toast from 'react-hot-toast'
import { useInvoices } from '../hooks'
import { Spinner, ErrorState, EmptyState, PageHeader, StatusBadge } from '../components/common'
import InvoiceTable from '../components/InvoiceTable'
import { REVIEW, PROCESSING } from '../services/mappers'
import { money, toCsv, download } from '../utils'

export default function Invoices() {
  const { invoices, error, reload } = useInvoices()
  const [q, setQ] = useState(''), [status, setStatus] = useState(''), [processing, setProcessing] = useState(''), [from, setFrom] = useState(''), [to, setTo] = useState('')
  const [sort, setSort] = useState({ key: 'updatedAt', dir: -1 })
  const rows = useMemo(() => {
    if (!invoices) return []
    const query = q.trim().toLowerCase()
    const value = (i, key) => key === 'vendor' ? i.vendor?.name : i[key]
    return invoices.filter(i => (!query || [i.vendor?.name, i.invoiceNumber, i.vendor?.taxId].some(v => String(v || '').toLowerCase().includes(query))) && (!status || i.reviewStatus === status) && (!processing || i.processingStatus === processing) && (!from || (i.invoiceDate && i.invoiceDate >= from)) && (!to || (i.invoiceDate && i.invoiceDate <= to)))
      .sort((a, b) => { const x = value(a, sort.key) ?? '', y = value(b, sort.key) ?? ''; return (x > y ? 1 : x < y ? -1 : 0) * sort.dir })
  }, [invoices, q, status, processing, from, to, sort])
  if (error) return <ErrorState message={error} onRetry={reload}/>
  if (!invoices) return <Spinner/>
  const clear = () => { setQ(''); setStatus(''); setProcessing(''); setFrom(''); setTo('') }
  const exportList = () => {
    try { const rowsCsv = ['invoice_number,vendor,invoice_date,due_date,currency,subtotal,tax,discount,total,processing_status,review_status', ...rows.map(i => [i.invoiceNumber, i.vendor?.name, i.invoiceDate, i.dueDate, i.currency, i.subtotal, i.taxAmount, i.discount, i.totalAmount, i.processingStatus, i.reviewStatus].map(v => { const s = String(v ?? ''); return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s }).join(','))].join('\r\n'); download('invoiceiq-register.csv', '\uFEFF' + rowsCsv, 'text/csv;charset=utf-8'); toast.success('Invoice register exported.') } catch { toast.error('Export could not be generated.') }
  }
  return <>
    <PageHeader title="Invoice register" subtitle="Search, filter, and review every document in one place." eyebrow="DOCUMENT MANAGEMENT">
      <button className="btn" onClick={exportList}><Download size={14}/>Export register</button><Link to="/upload" className="btn btn-p"><Upload size={14}/>Upload invoice</Link>
    </PageHeader>
    <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(3,minmax(0,1fr))' }}>
      <div className="stat-card"><div className="stat-label">Matching invoices</div><div className="stat-value">{rows.length}</div><div className="stat-foot">Of {invoices.length} total records</div></div>
      <div className="stat-card"><div className="stat-label">Total value in view</div><div className="stat-value" style={{fontSize: '21px'}}>{money(rows.reduce((sum, i) => sum + (Number(i.totalAmount) || 0), 0))}</div><div className="stat-foot">Based on current filters</div></div>
      <div className="stat-card"><div className="stat-label">Awaiting review</div><div className="stat-value">{rows.filter(i => ['pending', 'needs_review'].includes(i.reviewStatus)).length}</div><div className="stat-foot">Within matching records</div></div>
    </div>
    <section className="panel" style={{ marginBottom: 15 }}><div className="panel-title-row"><div><h2 className="panel-title"><SlidersHorizontal size={15} className="inline mr-2"/>Find invoices</h2><p className="panel-subtitle">Combine search and filters to narrow your register.</p></div><button className="btn" onClick={clear}><X size={13}/>Clear filters</button></div>
      <div className="filter-bar">
        <label><span className="filter-label">Search by vendor, invoice no. or tax ID</span><span className="relative block"><Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"/><input className="inp pl-9" placeholder="e.g. INV-1001" value={q} onChange={e => setQ(e.target.value)}/></span></label>
        <label><span className="filter-label">Review status</span><select className="inp" value={status} onChange={e => setStatus(e.target.value)}><option value="">All review statuses</option>{Object.entries(REVIEW).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
        <label><span className="filter-label">Processing status</span><select className="inp" value={processing} onChange={e => setProcessing(e.target.value)}><option value="">All processing statuses</option>{Object.entries(PROCESSING).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
        <label><span className="filter-label">Invoice date from</span><input className="inp" type="date" value={from} onChange={e => setFrom(e.target.value)}/></label>
        <label><span className="filter-label">Invoice date to</span><input className="inp" type="date" min={from || undefined} value={to} onChange={e => setTo(e.target.value)}/></label>
      </div>
    </section>
    <section className="panel table-panel"><div className="panel-title-row"><div><h2 className="panel-title">All invoices</h2><p className="panel-subtitle">Select a row’s arrow to open its review workspace.</p></div><span className="status-badge badge-grey"><FileSpreadsheet size={11}/>{rows.length} records</span></div><InvoiceTable rows={rows} sort={sort} onSort={key => setSort(s => ({ key, dir: s.key === key ? -s.dir : 1 }))}/><div className="table-foot"><span>Showing {rows.length} of {invoices.length} records</span><span><StatusBadge kind="review" value="needs_review"/> Requires attention</span></div></section>
    <p className="tiny-label mt-3">Deletion is not available because the current backend contract does not define a delete endpoint.</p>
  </>
}
