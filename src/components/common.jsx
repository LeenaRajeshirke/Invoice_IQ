import { LoaderCircle, AlertCircle, Inbox, AlertTriangle, Info, CheckCircle2 } from 'lucide-react'
import { PROCESSING, REVIEW } from '../services/mappers'
import { confPct, confLevel } from '../utils'

export const Spinner = ({ label = 'Loading your workspace…' }) => <div role="status" className="spinner"><LoaderCircle size={19} className="animate-spin" />{label}</div>
export function ErrorState({ message, onRetry }) { return <div role="alert" className="error-state"><div className="flex items-start gap-3"><AlertCircle size={20} className="shrink-0"/><div><b>We couldn’t load this information</b><p>{message}</p>{onRetry && <button className="btn" onClick={onRetry}>Try again</button>}</div></div></div> }
export function EmptyState({ title, text, children }) { return <div className="empty-state"><Inbox size={31} className="mx-auto"/><h3>{title}</h3><p>{text}</p>{children}</div> }
const reviewTone = { pending: 'grey', needs_review: 'amber', reviewed: 'green', rejected: 'red' }
const processingTone = { uploaded: 'grey', processing: 'blue', completed: 'green', failed: 'red' }
export function StatusBadge({ kind, value }) {
  const isReview = kind === 'review'
  const tone = (isReview ? reviewTone : processingTone)[value] || 'grey'
  const label = (isReview ? REVIEW : PROCESSING)[value] || String(value || 'Unknown')
  return <span className={`status-badge badge-${tone}`}>{label}</span>
}
export function ConfidenceBadge({ value }) {
  const p = confPct(value), level = confLevel(p)
  if (p == null) return <span className="tiny-label">No confidence data</span>
  const label = level === 'high' ? 'High' : level === 'mid' ? 'Moderate' : 'Low'
  return <span title="Model-reported confidence. Thresholds are display settings, not accuracy guarantees." className={`confidence-badge ${level === 'high' ? 'green' : level === 'mid' ? 'amber' : 'red'}`}>{label} · {p}%</span>
}
export function Warning({ w }) {
  const Icon = w.severity === 'info' ? Info : w.severity === 'error' ? AlertCircle : AlertTriangle
  const tone = w.severity === 'info' ? 'info' : w.severity === 'error' ? 'error' : ''
  return <li className={`warning-item ${tone}`}><Icon size={15} className="shrink-0 mt-0.5"/><span><b className="capitalize">{w.severity || 'warning'}:</b> {w.message}{w.field && <span className="muted"> (field: {w.field})</span>}</span></li>
}
export function ConfirmDialog({ open, title, text, onYes, onNo }) {
  if (!open) return null
  return <div role="dialog" aria-modal="true" aria-label={title} className="fixed inset-0 z-[100] bg-slate-950/45 grid place-items-center p-4"><div className="card w-full max-w-sm"><div className="flex items-center gap-2 mb-3"><span className="grid place-items-center w-9 h-9 rounded-xl bg-rose-50 text-rose-600"><AlertTriangle size={18}/></span><h2 className="panel-title">{title}</h2></div><p className="text-sm text-slate-600 leading-relaxed">{text}</p><div className="flex justify-end gap-2 mt-5"><button className="btn" onClick={onNo}>Cancel</button><button className="btn btn-danger" onClick={onYes}><CheckCircle2 size={14}/>Confirm</button></div></div></div>
}
export function PageHeader({ title, subtitle, eyebrow = 'INVOICEIQ WORKSPACE', children }) {
  return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1>{subtitle && <p>{subtitle}</p>}</div>{children && <div className="heading-actions">{children}</div>}</div>
}
