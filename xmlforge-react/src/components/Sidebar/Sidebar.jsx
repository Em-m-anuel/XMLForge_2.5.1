import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'

const icons = {
  logo: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>',
  db: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>',
  clock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>',
  shield2: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/><path d="m9 12 2 2 4-4"/></svg>',
  users: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 11h-6M16 5h6M19 2v6"/></svg>',
  gear: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>',
  logout: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/></svg>',
}

export function Sidebar({ active }) {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout, isAdmin } = useAuth()

  const isActive = (key) => {
    if (active) return active === key
    if (key === 'databases') return location.pathname.startsWith('/dashboard') || location.pathname.startsWith('/workspace')
    if (key === 'history') return location.pathname.startsWith('/history')
    if (key === 'audit') return location.pathname.startsWith('/audit')
    if (key === 'users') return location.pathname.startsWith('/users')
    return false
  }

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const navItem = (key, label, icon, onClick) => (
    <a
      key={key}
      className={`nav-item ${isActive(key) ? 'active' : ''}`}
      href="#"
      onClick={(e) => { e.preventDefault(); onClick() }}
    >
      <span dangerouslySetInnerHTML={{ __html: icon }} />
      <span>{label}</span>
    </a>
  )

  return (
    <>
      <div className="sidebar-logo">
        <div className="mark" dangerouslySetInnerHTML={{ __html: icons.logo }} />
        <span>XMLForge</span>
      </div>
      <div className="nav-group">
        {navItem('databases', 'Bases de données', icons.db, () => navigate('/dashboard'))}
        {isAdmin && navItem('history', 'Historique', icons.clock, () => navigate('/history'))}
        {isAdmin && navItem('audit', 'Audit', icons.shield2, () => navigate('/audit'))}
        {isAdmin && navItem('users', 'Utilisateurs', icons.users, () => navigate('/users'))}
        {navItem('settings', 'Paramètres', icons.gear, () => {})}
      </div>
      <div className="sidebar-spacer" />
      <div className="sidebar-bottom">
        <div className="sidebar-user">
          Connecté en tant que <b>{user?.full_name || 'Utilisateur'}</b>
          {isAdmin && <span style={{ marginLeft: '6px' }} className="badge badge-blue">ADMIN</span>}
        </div>
        {navItem('logout', 'Déconnexion', icons.logout, handleLogout)}
      </div>
    </>
  )
}
