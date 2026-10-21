import { useEffect, useMemo, useRef, useState } from 'react'
import { NavLink, Navigate, Route, Routes, Link, useLocation, useNavigate } from 'react-router-dom'
import { LayoutDashboard, FileText, Upload, Settings, Menu, X, Search, Bell, ChevronRight, Command, Moon, Sun, Building2, ArrowUpRight, Clock3, CheckCircle2, AlertTriangle, UserRound, SlidersHorizontal } from 'lucide-react'
import { config } from './config'
import { useInvoices } from './hooks'
import Dashboard from './pages/Dashboard'
import Invoices from './pages/Invoices'
import UploadPage from './pages/UploadPage'
import Review from './pages/Review'
import SettingsPage from './pages/SettingsPage'

const nav = [
  { to: '/dashboard', label: 'Overview', icon: LayoutDashboard },
  { to: '/invoices', label: 'Invoices', icon: FileText },
  { to: '/upload', label: 'Upload invoice', icon: Upload },
]
const pageNames = { '/dashboard': 'Overview', '/invoices': 'Invoices', '/upload': 'Upload invoice', '/settings': 'Settings' }

export default function App() {
  const [open, setOpen] = useState(false)
  const [theme, setTheme] = useState(() => window.localStorage.getItem('invoiceiq-theme') || 'light')
  const [searchOpen, setSearchOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const [readNotifications, setReadNotifications] = useState(() => window.localStorage.getItem('invoiceiq-notifications-read') === 'true')
  const [notificationsEnabled, setNotificationsEnabled] = useState(() => { try { return JSON.parse(window.localStorage.getItem('invoiceiq-preferences') || '{}').notifications !== false } catch { return true } })
  const [profileName, setProfileName] = useState(() => { try { return JSON.parse(window.localStorage.getItem('invoiceiq-profile') || '{}').name || 'Finance team' } catch { return 'Finance team' } })
  const searchRef = useRef(null)
  const location = useLocation()
  const navigate = useNavigate()
  const { invoices: loadedInvoices } = useInvoices()
  const invoices = loadedInvoices || []
  const title = location.pathname.includes('/review') ? 'Invoice review' : pageNames[location.pathname] || 'InvoiceIQ'
  const workspaceActive = ['/dashboard', '/invoices', '/upload'].includes(location.pathname) || location.pathname.includes('/review')
  const pending = invoices.filter(i => ['pending', 'needs_review'].includes(i.reviewStatus) || i.processingStatus === 'failed').slice(0, 5)
  const matches = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return []
    return invoices.filter(i => [i.invoiceNumber, i.vendor?.name, i.vendor?.taxId, i.customer?.name].some(v => String(v || '').toLowerCase().includes(q))).slice(0, 6)
  }, [invoices, query])

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    window.localStorage.setItem('invoiceiq-theme', theme)
  }, [theme])
  useEffect(() => {
    const themeHandler = e => setTheme(e.detail === 'dark' ? 'dark' : 'light')
    const prefsHandler = e => setNotificationsEnabled(e.detail?.notifications !== false)
    const profileHandler = e => setProfileName(e.detail?.name || 'Finance team')
    window.addEventListener('invoiceiq-theme-change', themeHandler)
    window.addEventListener('invoiceiq-preferences-change', prefsHandler)
    window.addEventListener('invoiceiq-profile-change', profileHandler)
    return () => { window.removeEventListener('invoiceiq-theme-change', themeHandler); window.removeEventListener('invoiceiq-preferences-change', prefsHandler); window.removeEventListener('invoiceiq-profile-change', profileHandler) }
  }, [])
  useEffect(() => {
    const handler = e => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); setSearchOpen(v => !v) }
      if (e.key === 'Escape') { setSearchOpen(false); setNotificationsOpen(false); setOpen(false) }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])
  useEffect(() => { if (searchOpen) window.setTimeout(() => searchRef.current?.focus(), 30); else setQuery('') }, [searchOpen])
  const openInvoice = id => { navigate(`/invoices/${id}/review`); setSearchOpen(false); setNotificationsOpen(false) }
  const markRead = () => { setReadNotifications(true); window.localStorage.setItem('invoiceiq-notifications-read', 'true') }

  return <div className="app-shell">
    {open && <button className="mobile-scrim" aria-label="Close navigation" onClick={() => setOpen(false)} />}
    <aside className={`sidebar ${open ? 'sidebar-open' : ''}`}>
      <Link to="/dashboard" className="brand" onClick={() => setOpen(false)}>
        <span className="brand-mark"><FileText size={21} strokeWidth={2.3} /></span>
        <span className="brand-name">invoice<span>iq</span><small>INTELLIGENT FINANCE</small></span>
      </Link>
      <NavLink to="/dashboard" onClick={() => setOpen(false)} className={`workspace-switcher ${workspaceActive ? 'workspace-current' : ''}`}>
        <span className="workspace-avatar"><Building2 size={17}/></span>
        <span className="workspace-copy"><b>Finance workspace</b><small>Workspace home</small></span>
        <ChevronRight size={15} className="workspace-chevron" />
      </NavLink>
      <nav className="side-nav" aria-label="Workspace navigation">{nav.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to} onClick={() => setOpen(false)} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}><Icon size={18} strokeWidth={1.9} /><span>{label}</span>{to === '/invoices' && <span className="nav-count">{invoices.length}</span>}</NavLink>)}</nav>
      <div className="sidebar-promo"><span className="promo-icon"><SlidersHorizontal size={17} /></span><b>Clearer invoice operations</b><p>Keep every document organized, verified, and ready for review.</p><Link to="/upload" onClick={() => setOpen(false)}>Add an invoice <ChevronRight size={14} /></Link></div>
      <div className="sidebar-bottom">
        <NavLink to="/settings" onClick={() => setOpen(false)} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}><Settings size={18} /><span>Settings</span></NavLink>
        <div className="profile-row"><span className="profile-avatar"><UserRound size={17}/></span><span className="profile-copy"><b>{profileName}</b><small>Workspace member</small></span><span className="online-dot" /></div>
      </div>
    </aside>
    <div className="main-area">
      <header className="topbar">
        <button className="icon-button mobile-menu" aria-label="Toggle navigation" onClick={() => setOpen(!open)}>{open ? <X size={19} /> : <Menu size={19} />}</button>
        <div className="breadcrumbs"><span>Finance workspace</span><ChevronRight size={14} /><b>{title}</b></div>
        <div className="topbar-actions">
          <button className="search-hint search-trigger" onClick={() => setSearchOpen(true)} aria-label="Open quick search"><Search size={15} /><span>Search anything</span><kbd><Command size={11} /> K</kbd></button>
          <span className={`mode-pill ${config.mode === 'mock' ? 'local' : 'live'}`} title={config.mode === 'mock' ? 'Using local workspace records' : `Connected to ${config.baseUrl}`}><i />{config.mode === 'mock' ? 'Local workspace' : 'API connected'}</span>
          <button className="icon-button" aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`} title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`} onClick={() => setTheme(v => v === 'dark' ? 'light' : 'dark')}>{theme === 'dark' ? <Sun size={18}/> : <Moon size={18}/>}</button>
          <div className="notification-wrap">
            <button className="icon-button notification-button" aria-label="Notifications" aria-expanded={notificationsOpen} onClick={() => setNotificationsOpen(v => !v)}><Bell size={18} />{notificationsEnabled && pending.length > 0 && !readNotifications && <i />}</button>
            {notificationsOpen && <div className="notification-popover">
              <div className="popover-heading"><div><b>Notifications</b><small>{pending.length ? `${pending.length} items need attention` : 'You are all caught up'}</small></div><button className="text-action" onClick={markRead}>Mark read</button></div>
              {!notificationsEnabled ? <div className="popover-empty"><Bell size={22}/><span>In-app notifications are turned off in Settings.</span></div> : pending.length ? pending.map(i => <button className="notification-item" key={i.id} onClick={() => openInvoice(i.id)}><span className={`notification-symbol ${i.processingStatus === 'failed' ? 'danger' : ''}`}>{i.processingStatus === 'failed' ? <AlertTriangle size={16}/> : <Clock3 size={16}/>}</span><span><b>{i.vendor?.name || i.invoiceNumber || 'Invoice requires review'}</b><small>{i.processingStatus === 'failed' ? 'Processing needs attention' : 'Waiting for review'} · {i.invoiceNumber || 'Invoice number pending'}</small></span><ArrowUpRight size={14}/></button>) : <div className="popover-empty"><CheckCircle2 size={22}/><span>No pending notifications</span></div>}
              <Link to="/invoices" className="popover-footer" onClick={() => setNotificationsOpen(false)}>View invoice register <ChevronRight size={14}/></Link>
            </div>}
          </div>
        </div>
      </header>
      <main className="page-content"><Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/invoices" element={<Invoices />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/invoices/:id/review" element={<Review />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes><footer className="app-footer"><span>© 2026 InvoiceIQ</span><span>Built for accuracy, designed for people.</span></footer></main>
    </div>
    {searchOpen && <div className="search-overlay" role="presentation" onMouseDown={e => { if (e.target === e.currentTarget) setSearchOpen(false) }}><section className="search-dialog" role="dialog" aria-modal="true" aria-label="Quick search"><div className="search-dialog-input"><Search size={19}/><input ref={searchRef} value={query} onChange={e => setQuery(e.target.value)} placeholder="Search invoices, vendors, tax IDs…" aria-label="Search invoices"/><kbd>ESC</kbd><button className="icon-button" aria-label="Close search" onClick={() => setSearchOpen(false)}><X size={17}/></button></div>
      {query.trim() ? <div className="search-results">{matches.length ? matches.map(i => <button key={i.id} className="search-result" onClick={() => openInvoice(i.id)}><span className="search-result-icon"><FileText size={17}/></span><span><b>{i.vendor?.name || 'Unnamed vendor'}</b><small>{i.invoiceNumber || 'Invoice number pending'} · {i.customer?.name || 'Customer not specified'}</small></span><span className="search-result-amount">{i.totalAmount != null ? new Intl.NumberFormat('en-IN',{style:'currency',currency:i.currency||'INR',maximumFractionDigits:0}).format(i.totalAmount) : '—'}</span><ArrowUpRight size={15}/></button>) : <div className="popover-empty">No invoices match “{query}”.</div>}</div> : <div className="search-shortcuts"><span>QUICK LINKS</span><button onClick={() => { setSearchOpen(false); navigate('/dashboard') }}><LayoutDashboard size={16}/>Overview<kbd>↵</kbd></button><button onClick={() => { setSearchOpen(false); navigate('/invoices') }}><FileText size={16}/>Invoice register<kbd>↵</kbd></button><button onClick={() => { setSearchOpen(false); navigate('/upload') }}><Upload size={16}/>Upload invoice<kbd>↵</kbd></button><button onClick={() => { setSearchOpen(false); navigate('/settings') }}><Settings size={16}/>Settings<kbd>↵</kbd></button></div>}
      <div className="search-dialog-foot"><span>Search by invoice number, vendor, customer, or tax ID</span><span><Command size={11}/> K to open</span></div></section></div>}
  </div>
}
