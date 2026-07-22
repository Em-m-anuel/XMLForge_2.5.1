import { Badge } from '../Badge/Badge'
import './Navbar.css'

const IconSearch = <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>

export function Navbar({ searchValue, onSearchChange, userInitials='NX' }){
  return (
    <div className="topbar">
      <label className="topbar-search">
        {IconSearch}
        <input
          type="text"
          placeholder="Rechercher une base de données..."
          value={searchValue}
          onChange={e=>onSearchChange?.(e.target.value)}
        />
      </label>
      <div className="topbar-right">
        <Badge variant="green" dot="#22C55E">Connecté</Badge>
        <div className="avatar">{userInitials}</div>
      </div>
    </div>
  )
}
