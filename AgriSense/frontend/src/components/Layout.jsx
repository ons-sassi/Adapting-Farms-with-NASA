import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { BarChart3, Bot, Headphones, Home, LogOut, Map, Settings, Sprout, Menu, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { demoUser } from '../data/demo/demoData.js'
import { api, DATA_MODE, getUser, onAuthChange } from '../api/client.js'

const NAV = [
  { to: '/', label: 'Accueil', icon: Home, end: true },
  { to: '/terrains', label: 'Mes terrains', icon: Map },
  { to: '/analyses', label: 'Analyses', icon: BarChart3 },
  { to: '/chatbot', label: 'Chatbot', icon: Bot },
  { to: '/parametres', label: 'Paramètres', icon: Settings },
]

export function Logo({ compact = false }) {
  return (
    <div className="logo">
      <span className="logo-mark"><Sprout size={compact ? 22 : 26} /></span>
      {!compact && (
        <span>
          <strong>AgriSense</strong>
          <small>Choisir sa rotation</small>
        </span>
      )}
    </div>
  )
}

export default function Layout() {
  const [open, setOpen] = useState(false)
  const location = useLocation()
  const isAnalysis = location.pathname.startsWith('/analyse')
  const isHome = location.pathname === '/'
  const [user, setUser] = useState(DATA_MODE === 'demo' ? { full_name: demoUser.name } : getUser())
  useEffect(() => onAuthChange((u) => DATA_MODE === 'api' && setUser(u)), [])

  return (
    <div className="app-shell">
      <aside className={`sidebar ${open ? 'open' : ''}`}>
        <div className="sidebar-head">
          <Logo />
          <button className="icon-btn mobile-only" onClick={() => setOpen(false)} aria-label="Fermer le menu"><X size={20} /></button>
        </div>
        <nav>
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} onClick={() => setOpen(false)}
              className={({ isActive }) => `nav-item ${isActive || (to === '/analyses' && isAnalysis) ? 'active' : ''}`}>
              <Icon size={19} /> <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          {user && (
            <div className="user-box">
              <span className="avatar">{user.full_name?.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase()}</span>
              <span className="user-name">{user.full_name}{DATA_MODE === 'demo' && <small>Mode démo</small>}</span>
              {DATA_MODE === 'api' && (
                <button className="icon-btn" onClick={() => api.logout()} aria-label="Se déconnecter" title="Se déconnecter"><LogOut size={18} /></button>
              )}
            </div>
          )}
          <NavLink to="/chatbot" className="help-card" onClick={() => setOpen(false)}>
            <Headphones size={20} />
            <span><strong>Besoin d'aide ?</strong><small>Notre assistant est là</small></span>
          </NavLink>
        </div>
      </aside>
      {open && <div className="backdrop" onClick={() => setOpen(false)} />}

      <main className="main">
        {isHome ? (
          <button className="icon-btn mobile-only menu-float" onClick={() => setOpen(true)} aria-label="Ouvrir le menu"><Menu size={22} /></button>
        ) : (
          <header className="topbar">
            <button className="icon-btn mobile-only" onClick={() => setOpen(true)} aria-label="Ouvrir le menu"><Menu size={22} /></button>
            <div className="topbar-right">
            </div>
          </header>
        )}
        <div className={`page ${isHome ? 'page-home' : ''}`}>
          <Outlet />
        </div>
      </main>
    </div>
  )
}
