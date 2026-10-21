import { Link } from 'react-router-dom'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell } from 'recharts'
import { Upload, ArrowUpRight, FileCheck2, Clock3, AlertCircle, Files, CircleDollarSign, ArrowRight, Sparkles, ShieldCheck } from 'lucide-react'
import { useInvoices } from '../hooks'
import { Spinner, ErrorState, EmptyState, PageHeader, StatusBadge } from '../components/common'
import InvoiceTable from '../components/InvoiceTable'
import { money, fmtDate } from '../utils'

export default function Dashboard() {
  const { invoices: inv, error, reload } = useInvoices()
  if (error) return <ErrorState message={error} onRetry={reload}/>
  if (!inv) return <Spinner/>
  const count = fn => inv.filter(fn).length
  const awaiting = count(i => ['pending', 'needs_review'].includes(i.reviewStatus))
  const totalValue = inv.reduce((sum, i) => sum + (Number(i.totalAmount) || 0), 0)
  const stats = [
    { label: 'Total invoices', value: inv.length, note: 'Documents in workspace', icon: Files, tone: 'purple' },
    { label: 'Awaiting review', value: awaiting, note: 'Need a human decision', icon: Clock3, tone: 'amber' },
    { label: 'Approved invoices', value: count(i => i.reviewStatus === 'reviewed'), note: 'Reviewed and confirmed', icon: FileCheck2, tone: 'green' },
    { label: 'Needs attention', value: count(i => i.processingStatus === 'failed' || i.reviewStatus === 'rejected'), note: 'Failed or rejected records', icon: AlertCircle, tone: 'blue' },
  ]
  const chart = [
    { name: 'Uploaded', count: count(i => i.processingStatus === 'uploaded'), fill: '#aaa2fa' },
    { name: 'Processing', count: count(i => i.processingStatus === 'processing'), fill: '#7f76e8' },
    { name: 'Completed', count: count(i => i.processingStatus === 'completed'), fill: '#4f46c8' },
    { name: 'Failed', count: count(i => i.processingStatus === 'failed'), fill: '#e78d96' },
  ]
  const recent = [...inv].sort((a, b) => String(b.updatedAt || '').localeCompare(String(a.updatedAt || ''))).slice(0, 5)
  const priority = inv.filter(i => ['pending', 'needs_review'].includes(i.reviewStatus) || i.processingStatus === 'failed').sort((a, b) => Number(a.totalAmount || 0) - Number(b.totalAmount || 0)).slice(0, 4)
  return <>
    <PageHeader title="Good to see you again" subtitle="Here’s what’s happening with your invoice operations today." eyebrow="FINANCE OVERVIEW">
      <Link to="/invoices" className="btn"><Files size={15}/>All invoices</Link><Link to="/upload" className="btn btn-p"><Upload size={15}/>Upload invoice</Link>
    </PageHeader>
    <section className="welcome-banner"><div className="welcome-copy"><div className="eyebrow">YOUR WORKFLOW, AT A GLANCE</div><h2>Less manual work. More financial clarity.</h2><p>Keep invoices organized, verify extracted details, and move every document toward a confident decision.</p></div><Link to="/upload" className="btn"><Upload size={15}/>Start with an invoice <ArrowUpRight size={14}/></Link><Sparkles className="welcome-symbol" size={95}/></section>
    <section className="stats-grid" aria-label="Invoice summary">{stats.map(({ label, value, note, icon: Icon, tone }) => <article className={`stat-card stat-${tone}`} key={label}><div className="stat-top"><span className="stat-label">{label}</span><span className="stat-icon"><Icon size={17}/></span></div><div className="stat-value">{value.toLocaleString('en-IN')}</div><div className="stat-foot">{note}</div></article>)}</section>
    <section className="dashboard-grid">
      <div className="panel"><div className="panel-title-row"><div><h2 className="panel-title">Processing overview</h2><p className="panel-subtitle">How documents are moving through your workflow</p></div><span className="status-badge badge-blue">{inv.length} total</span></div>
        <div className="chart-wrap">{inv.length ? <ResponsiveContainer width="100%" height="100%"><BarChart data={chart} margin={{ top: 10, right: 8, left: -22, bottom: 0 }} barSize={30}><CartesianGrid stroke="#edf0f6" strokeDasharray="3 5" vertical={false}/><XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#8994a8', fontSize: 10 }} dy={8}/><YAxis allowDecimals={false} axisLine={false} tickLine={false} tick={{ fill: '#a1aabc', fontSize: 10 }}/><Tooltip cursor={{ fill: '#f7f7fd' }} contentStyle={{ border: '1px solid #e8ecf3', borderRadius: 10, fontSize: 11 }}/><Bar dataKey="count" name="Invoices" radius={[6, 6, 0, 0]}>{chart.map(d => <Cell key={d.name} fill={d.fill}/>)}</Bar></BarChart></ResponsiveContainer> : <EmptyState title="No processing data yet" text="Upload a document to start your workflow."/>}</div>
      </div>
      <div className="panel"><div className="panel-title-row"><div><h2 className="panel-title">Review queue</h2><p className="panel-subtitle">Documents that may need your attention</p></div><span className="status-badge badge-amber">{awaiting} pending</span></div>
        {priority.length ? <div className="review-priority-list">{priority.map(i => <div className="priority-item" key={i.id}><span className="priority-mark"><AlertCircle size={16}/></span><div className="priority-copy"><b>{i.vendor?.name || i.invoiceNumber || 'Invoice needs review'}</b><small>{i.invoiceNumber || 'Number not detected'} · {fmtDate(i.invoiceDate)}</small></div><div className="priority-amount">{money(i.totalAmount, i.currency)}<small><StatusBadge kind="review" value={i.reviewStatus}/></small></div><Link to={`/invoices/${i.id}/review`} className="link-muted" aria-label="Review invoice"><ArrowUpRight size={15}/></Link></div>)}</div> : <EmptyState title="Queue is clear" text="There are no invoices waiting for review."/>}
        <Link className="link-muted mt-3" to="/invoices">Open invoice register <ArrowRight size={14}/></Link>
      </div>
    </section>
    <section className="panel table-panel"><div className="panel-title-row"><div><h2 className="panel-title">Recently updated</h2><p className="panel-subtitle">Latest changes across your invoice register</p></div><Link to="/invoices" className="link-muted">View all invoices <ArrowRight size={14}/></Link></div>
      {recent.length ? <InvoiceTable rows={recent}/> : <EmptyState title="Your workspace is ready" text="Upload your first invoice to see it appear here."><Link to="/upload" className="btn btn-p"><Upload size={14}/>Upload invoice</Link></EmptyState>}
      <div className="table-foot"><span><ShieldCheck size={12} className="inline mr-1"/>Human review stays in control</span><span>Workspace invoice value · {money(totalValue)}</span></div>
    </section>
  </>
}
