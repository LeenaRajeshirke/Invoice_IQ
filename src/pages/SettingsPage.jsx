import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { UserRound, ShieldCheck, Server, Gauge, ExternalLink, CheckCircle2, FileText, Save, Moon, Sun, SlidersHorizontal, KeyRound, MonitorCog } from 'lucide-react'
import toast from 'react-hot-toast'
import { config } from '../config'
import { PageHeader } from '../components/common'

const readPrefs = () => {
  try { return { notifications: true, emailDigest: false, compactTables: false, ...JSON.parse(localStorage.getItem('invoiceiq-preferences') || '{}') } }
  catch { return { notifications: true, emailDigest: false, compactTables: false } }
}
function ToggleRow({ title, description, checked, onChange }) {
  return <label className="preference-row"><span><b>{title}</b><small>{description}</small></span><input className="switch-input" type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} /><span className="switch-ui" aria-hidden="true"/></label>
}
function InfoRow({ label, value }) { return <div className="settings-row"><span>{label}</span><b>{value}</b></div> }

export default function SettingsPage() {
  const [profile, setProfile] = useState(() => {
    try { return { name: 'Finance team', email: 'finance@company.com', role: 'Workspace administrator', ...JSON.parse(localStorage.getItem('invoiceiq-profile') || '{}') } }
    catch { return { name: 'Finance team', email: 'finance@company.com', role: 'Workspace administrator' } }
  })
  const [prefs, setPrefs] = useState(readPrefs)
  const [theme, setTheme] = useState(() => localStorage.getItem('invoiceiq-theme') || 'light')
  useEffect(() => {
    localStorage.setItem('invoiceiq-preferences', JSON.stringify(prefs))
    document.documentElement.dataset.compactTables = prefs.compactTables ? 'true' : 'false'
    window.dispatchEvent(new CustomEvent('invoiceiq-preferences-change', { detail: prefs }))
  }, [prefs])
  const changeTheme = next => {
    setTheme(next); localStorage.setItem('invoiceiq-theme', next)
    window.dispatchEvent(new CustomEvent('invoiceiq-theme-change', { detail: next }))
    document.documentElement.dataset.theme = next
  }
  const saveProfile = e => {
    e.preventDefault()
    localStorage.setItem('invoiceiq-profile', JSON.stringify(profile))
    window.dispatchEvent(new CustomEvent('invoiceiq-profile-change', { detail: profile }))
    toast.success('Profile preferences saved on this device.')
  }
  const setPref = (key, value) => setPrefs(p => ({ ...p, [key]: value }))
  return <>
    <PageHeader title="Settings" subtitle="Manage your account, workspace preferences, and application connection." eyebrow="PREFERENCES & ADMINISTRATION" />
    <div className="settings-tabs"><a href="#account" className="settings-tab active"><UserRound size={15}/>Account</a><a href="#preferences" className="settings-tab"><SlidersHorizontal size={15}/>Preferences</a><a href="#connection" className="settings-tab"><Server size={15}/>Connections</a><a href="#security" className="settings-tab"><ShieldCheck size={15}/>Security</a></div>
    <div className="settings-grid">
      <div className="settings-main-column">
        <section className="panel settings-panel" id="account">
          <div className="settings-section-heading"><span className="settings-section-icon"><UserRound size={18}/></span><div><h2 className="panel-title">Account profile</h2><p className="panel-subtitle">Personalize the details shown for your workspace profile.</p></div></div>
          <form onSubmit={saveProfile} className="settings-form">
            <div className="profile-preview"><span className="profile-avatar large"><UserRound size={22}/></span><div><b>{profile.name || 'Workspace member'}</b><small>{profile.role}</small></div><span className="status-badge badge-green">Active</span></div>
            <label className="setting-field"><span>Display name</span><input className="inp" value={profile.name} onChange={e => setProfile(s => ({ ...s, name: e.target.value }))} required maxLength={80}/></label>
            <label className="setting-field"><span>Work email</span><input className="inp" type="email" value={profile.email} onChange={e => setProfile(s => ({ ...s, email: e.target.value }))} required maxLength={120}/></label>
            <label className="setting-field"><span>Role</span><input className="inp" value={profile.role} onChange={e => setProfile(s => ({ ...s, role: e.target.value }))} maxLength={80}/></label>
            <div className="settings-form-actions"><span className="tiny-label">Profile details are stored locally in this browser.</span><button className="btn btn-p" type="submit"><Save size={14}/>Save profile</button></div>
          </form>
        </section>
        <section className="panel settings-panel" id="preferences">
          <div className="settings-section-heading"><span className="settings-section-icon"><SlidersHorizontal size={18}/></span><div><h2 className="panel-title">Workspace preferences</h2><p className="panel-subtitle">Control how InvoiceIQ looks and keeps you informed.</p></div></div>
          <div className="theme-choice-row"><div><b>Appearance</b><small>Choose a theme for your workspace.</small></div><div className="theme-choice"><button className={theme === 'light' ? 'selected' : ''} onClick={() => changeTheme('light')}><Sun size={15}/>Light</button><button className={theme === 'dark' ? 'selected' : ''} onClick={() => changeTheme('dark')}><Moon size={15}/>Dark</button></div></div>
          <ToggleRow title="In-app notifications" description="Show pending review and processing alerts." checked={prefs.notifications} onChange={v => setPref('notifications', v)}/>
          <ToggleRow title="Email digest preference" description="Save your preference for a future notification integration." checked={prefs.emailDigest} onChange={v => setPref('emailDigest', v)}/>
          <ToggleRow title="Compact invoice tables" description="Reduce row spacing to see more invoices at once." checked={prefs.compactTables} onChange={v => setPref('compactTables', v)}/>
        </section>
        <section className="panel settings-panel" id="security">
          <div className="settings-section-heading"><span className="settings-section-icon"><KeyRound size={18}/></span><div><h2 className="panel-title">Security & privacy</h2><p className="panel-subtitle">A few important notes about the current frontend.</p></div></div>
          <div className="security-note"><ShieldCheck size={18}/><div><b>Review before approval</b><p>Invoice fields should be checked by a person before they are used for financial decisions.</p></div></div>
          <div className="security-note"><KeyRound size={18}/><div><b>Keep credentials private</b><p>Never place private API keys or service credentials in frontend environment variables.</p></div></div>
          <div className="security-note"><MonitorCog size={18}/><div><b>Local profile settings</b><p>Profile and appearance preferences are stored in this browser; authentication and server-side account management require backend support.</p></div></div>
        </section>
      </div>
      <aside className="settings-side-column">
        <div className="settings-hero"><span className="settings-hero-icon"><ShieldCheck size={22}/></span><div className="eyebrow">INVOICEIQ WORKSPACE</div><h2>Your workflow. Your control.</h2><p>Keep financial documents organized and put human verification at the center of every approval.</p></div>
        <section className="panel settings-panel" id="connection">
          <div className="settings-section-heading"><span className="settings-section-icon"><Server size={18}/></span><div><h2 className="panel-title">API connection</h2><p className="panel-subtitle">Current application configuration.</p></div></div>
          <div className="connection-status"><span className={`connection-dot ${config.mode === 'mock' ? 'local' : 'connected'}`}/><div><b>{config.mode === 'mock' ? 'Local workspace mode' : 'API configured'}</b><small>{config.mode === 'mock' ? 'Using local workspace records. Uploads are not sent to an extraction service in this mode.' : 'The app is configured to use the backend service.'}</small></div></div>
          <InfoRow label="Application version" value="0.1.0"/><InfoRow label="API mode" value={config.mode === 'mock' ? 'Local' : 'Connected'}/><InfoRow label="Backend URL" value={config.baseUrl}/><InfoRow label="Upload limit" value={`${config.maxMB} MB`}/><InfoRow label="High confidence threshold" value={`${config.high}%`}/><InfoRow label="Moderate confidence threshold" value={`${config.mid}%`}/>
          <div className="notice info mt-4 mb-0"><Gauge size={16} className="shrink-0 mt-0.5"/><span>Confidence thresholds only change the displayed label. They do not guarantee extraction accuracy.</span></div>
          <p className="tiny-label mt-3">To switch connection mode, update <code>.env</code> and restart the development server.</p>
        </section>
        <section className="panel settings-panel">
          <h2 className="panel-title"><FileText size={16} className="inline mr-2"/>Quick actions</h2><p className="panel-subtitle mb-4">Continue working with your invoices.</p>
          <div className="settings-shortcuts"><Link to="/invoices" className="btn justify-between">Open invoice register <ExternalLink size={13}/></Link><Link to="/upload" className="btn justify-between">Upload a document <ExternalLink size={13}/></Link></div>
          <div className="settings-secure-foot"><CheckCircle2 size={14}/>No backend secrets are displayed here.</div>
        </section>
      </aside>
    </div>
  </>
}
