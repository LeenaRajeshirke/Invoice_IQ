import { Link } from 'react-router-dom'
import { ArrowDownUp, ArrowUpRight, FileText } from 'lucide-react'
import { StatusBadge } from './common'
import { money, fmtDate } from '../utils'

const initials = name => (name || 'U').trim().split(/\s+/).slice(0, 2).map(x => x[0]).join('').toUpperCase()
export default function InvoiceTable({ rows = [], sort, onSort }) {
  const th = (key, label) => <th>{onSort ? <button className="sort-btn" onClick={() => onSort(key)}>{label}<ArrowDownUp size={11}/>{sort?.key === key ? (sort.dir > 0 ? '↑' : '↓') : ''}</button> : label}</th>
  if (!rows.length) return <div className="empty-state"><FileText size={30} className="mx-auto"/><h3>No invoices to show</h3><p>Try adjusting your filters or upload an invoice to get started.</p></div>
  return <div className="table-wrap"><table className="invoice-table"><thead><tr>{th('invoiceNumber', 'INVOICE')}{th('vendor', 'VENDOR')}{th('invoiceDate', 'INVOICE DATE')}{th('totalAmount', 'TOTAL AMOUNT')}<th>PROCESSING</th><th>REVIEW STATUS</th>{th('updatedAt', 'LAST UPDATED')}<th aria-label="Actions"/></tr></thead><tbody>{rows.map(i => <tr key={i.id}>
    <td className="invoice-id">{i.invoiceNumber || <span className="muted">Draft invoice</span>}<div className="vendor-sub">{`ID · ${String(i.id).slice(0, 12)}`}</div></td>
    <td><div className="vendor-cell"><span className="vendor-avatar">{initials(i.vendor?.name)}</span><span><span className="vendor-name">{i.vendor?.name || 'Vendor not identified'}</span><span className="vendor-sub">{i.vendor?.taxId || 'Vendor details'}</span></span></div></td>
    <td>{fmtDate(i.invoiceDate)}</td><td className="invoice-id">{money(i.totalAmount, i.currency)}</td><td><StatusBadge value={i.processingStatus}/></td><td><StatusBadge kind="review" value={i.reviewStatus}/></td><td>{fmtDate(i.updatedAt)}</td>
    <td><Link className="table-action" to={`/invoices/${i.id}/review`} aria-label={`Review ${i.invoiceNumber || 'invoice'}`} title="Open invoice review"><ArrowUpRight size={15}/></Link></td>
  </tr>)}</tbody></table></div>
}
