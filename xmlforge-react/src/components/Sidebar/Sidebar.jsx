import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import './Sidebar.css'

const IconDb = <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>
const IconSettings = <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
const IconLogout = <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/></svg>
const IconLogo = <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>
const IconHistory = <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
const IconShield = <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/></svg>

export function Sidebar({ onSettings }){
  const navigate = useNavigate()
  const location = useLocation()
  const { logout, user, isPrivileged } = useAuth()
  const isActive = (path)=> location.pathname.startsWith(path)

  const handleLogout = async ()=>{
    await logout()
    navigate('/login')
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div className="mark">{IconLogo}</div>
        <span>XMLForge</span>
      </div>

      <div className="nav-group">
        <button className={`nav-item ${isActive('/dashboard') ? 'active' : ''}`} onClick={()=>navigate('/dashboard')}>
          {IconDb}<span>Bases de données</span>
        </button>

        {/* Historique et Audit visibles uniquement pour nyx@xmlforge.io - préparé pour futur système de rôles */}
        {isPrivileged && (
          <>
            <button className={`nav-item ${isActive('/history') ? 'active' : ''}`} onClick={()=>navigate('/history')}>
              {IconHistory}<span>Historique</span>
            </button>
            <button className={`nav-item ${isActive('/audit') ? 'active' : ''}`} onClick={()=>navigate('/audit')}>
              {IconShield}<span>Audit Log</span>
            </button>
          </>
        )}

        <button className="nav-item" onClick={onSettings}>
          {IconSettings}<span>Paramètres</span>
        </button>
      </div>

      <div className="sidebar-spacer" />

      <div className="sidebar-bottom">
        <div style={{padding:'8px 10px', fontSize:11, color:'var(--text-tertiary)'}}>
          <div style={{fontWeight:600, color:'var(--text-secondary)'}}>{user?.full_name || 'Utilisateur'}</div>
          <div style={{fontSize:10, fontFamily:'var(--font-mono)'}}>{user?.email || ''}</div>
          {isPrivileged && <div style={{fontSize:9, marginTop:4, padding:'2px 6px', background:'var(--accent-soft)', color:'#7CACFB', borderRadius:100, display:'inline-block'}}>ADMIN • nyx@xmlforge.io</div>}
        </div>
        <button className="nav-item" onClick={handleLogout}>
          {IconLogout}<span>Déconnexion</span>
        </button>
      </div>
    </aside>
  )
}
