import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { UploadCloud, X, LoaderCircle, FileText, ShieldCheck, ScanText, CheckCircle2, Info, FileImage, ArrowRight } from 'lucide-react'
import { PageHeader } from '../components/common'
import { validateFile, sizeStr } from '../utils'
import { invoiceApi, errMsg } from '../services/invoiceApi'

export default function UploadPage() {
  const [file, setFile] = useState(null), [err, setErr] = useState(null), [busy, setBusy] = useState(false), [prog, setProg] = useState(null), [drag, setDrag] = useState(false)
  const ref = useRef(null), nav = useNavigate()
  const pick = f => { if (!f) return; const message = validateFile(f); setErr(message); setFile(message ? null : f) }
  async function submit() {
    if (!file || busy) return
    setBusy(true); setProg(0)
    try { const record = await invoiceApi.upload(file, setProg); toast.success('Invoice added to your workspace.'); nav(`/invoices/${record.id}/review`) }
    catch (e) { setErr(errMsg(e)); toast.error('Upload failed. Check the connection and try again.') }
    finally { setBusy(false) }
  }
  return <>
    <PageHeader title="Upload an invoice" subtitle="Add a document to your workspace and prepare it for structured review." eyebrow="DOCUMENT INTAKE" />
    <div className="upload-layout">
      <section className="panel"><div className="panel-title-row"><div><h2 className="panel-title">Add your document</h2><p className="panel-subtitle">Choose a file from your device or drop it below.</p></div><span className="status-badge badge-blue">Step 1 of 2</span></div>
        <div className={`dropzone ${drag ? 'dragging' : ''}`} onDragOver={e => { e.preventDefault(); setDrag(true) }} onDragLeave={e => { if (!e.currentTarget.contains(e.relatedTarget)) setDrag(false) }} onDrop={e => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files?.[0]) }}>
          <div className="upload-icon"><UploadCloud size={29}/></div><h2>Drop your invoice here</h2><p>Drag a document into this area, or browse your device to select a file for upload.</p>
          <button className="btn btn-p" onClick={() => ref.current?.click()}><FileText size={15}/>Browse files</button><input ref={ref} type="file" hidden accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg" onChange={e => { pick(e.target.files?.[0]); e.target.value = '' }} aria-label="Select invoice file"/>
          <div className="tiny-label mt-4">Supported formats: PDF, PNG, JPG, JPEG · Maximum file size: {config.maxMB} MB</div>
        </div>
        {err && <div className="notice error mt-3" role="alert"><Info size={16}/><span>{err}</span></div>}
        {file && <div className="file-chip"><span className="file-icon">{file.type === 'application/pdf' ? <FileText size={20}/> : <FileImage size={20}/>}</span><div className="file-info"><b>{file.name}</b><small>{sizeStr(file.size)} · {file.type || 'Unknown file type'}{busy && prog != null ? ` · Uploading ${prog}%` : ' · Ready to upload'}</small>{busy && <div className="h-1.5 rounded-full bg-slate-100 mt-2 overflow-hidden"><div className="h-full bg-violet-500 transition-all" style={{ width: `${prog || 0}%` }}/></div>}</div><button className="icon-button" disabled={busy} aria-label="Remove selected file" onClick={() => { setFile(null); setErr(null) }}><X size={16}/></button></div>}
        <div className="flex flex-wrap items-center justify-between gap-3 mt-4"><span className="tiny-label">Only upload documents you’re authorized to process.</span><button className="btn btn-p" disabled={!file || busy} onClick={submit}>{busy ? <LoaderCircle size={15} className="animate-spin"/> : <ArrowRight size={15}/>}{busy ? 'Uploading document…' : 'Continue to review'}</button></div>
      </section>
      <aside className="panel"><div className="panel-title-row"><div><h2 className="panel-title">What happens next?</h2><p className="panel-subtitle">A transparent, human-in-the-loop workflow.</p></div></div><div className="upload-tips">
        <div className="tip-row"><span className="tip-icon"><UploadCloud size={16}/></span><div><b>1. Securely add a document</b><p>Choose an invoice file in one of the supported formats. The backend should validate it again in live mode.</p></div></div>
        <div className="tip-row"><span className="tip-icon"><ScanText size={16}/></span><div><b>2. Extract and structure</b><p>In live mode, the connected backend is responsible for OCR or AI extraction and returning structured fields.</p></div></div>
        <div className="tip-row"><span className="tip-icon"><ShieldCheck size={16}/></span><div><b>3. Verify before approval</b><p>Review the document, correct any uncertain values, and confirm the invoice status.</p></div></div>
        <div className="tip-row"><span className="tip-icon"><CheckCircle2 size={16}/></span><div><b>4. Export clean data</b><p>Download the reviewed invoice as CSV or JSON for downstream workflows.</p></div></div>
      </div><div className="notice info mt-5 mb-0"><Info size={16} className="shrink-0 mt-0.5"/><span><b>Good to know:</b> Confidence scores and extracted values only appear when supplied by the connected backend.</span></div></aside>
    </div>
  </>
}
