import { Navigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'

export function AdminRoute({ children }) {
  const { isAdmin, loading, isAuthenticated } = useAuth()

  if (loading) {
    return (
      <div style={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg)', color: 'var(--text)' }}>
        <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>Vérification des privilèges...</span>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  if (!isAdmin) {
    return (
      <div style={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg)', flexDirection: 'column', gap: '12px' }}>
        <div style={{ fontSize: '48px' }}>🔒</div>
        <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text)' }}>Accès refusé</div>
        <div style={{ fontSize: '13px', color: 'var(--text-secondary)', maxWidth: '320px', textAlign: 'center' }}>
          Cette page nécessite le rôle <b>ADMIN</b> attribué par le backend. Vous n'avez pas les privilèges requis.
        </div>
        <button className="btn btn-primary" onClick={() => window.location.href = '/dashboard'}>Retour Dashboard</button>
      </div>
    )
  }

  return children
}
