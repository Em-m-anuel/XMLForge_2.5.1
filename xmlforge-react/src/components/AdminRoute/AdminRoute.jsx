import { Navigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { Loader } from '../Loader/Loader'
import { EmptyState } from '../EmptyState/EmptyState'
import { Icons } from '../../utils/icons'

export function AdminRoute({ children }){
  const { isPrivileged, isAuthenticated, loading, user } = useAuth()

  if(loading){
    return (
      <div style={{height:'100vh', display:'flex', alignItems:'center', justifyContent:'center', background:'var(--bg)'}}>
        <Loader size={28} />
      </div>
    )
  }

  if(!isAuthenticated){
    return <Navigate to="/login" replace />
  }

  if(!isPrivileged){
    // Page 403 intégrée, même identité visuelle
    return (
      <div style={{height:'100vh', display:'flex', flexDirection:'column', background:'var(--bg)'}}>
        <div style={{flex:1, display:'flex', alignItems:'center', justifyContent:'center', padding:20}}>
          <div style={{maxWidth:460, width:'100%', textAlign:'center'}}>
            <EmptyState
              icon={Icons.shield}
              title="Accès restreint"
              description={`Cette page est réservée à l'administrateur. Connecté en tant que ${user?.email || 'utilisateur'} vous n'avez pas les permissions nécessaires. Votre tentative a été enregistrée dans l'audit log.`}
            />
            <div style={{marginTop:16, display:'flex', gap:10, justifyContent:'center'}}>
              <a href="/dashboard" className="btn btn-primary" style={{textDecoration:'none'}}>← Retour Dashboard</a>
            </div>
            <div style={{marginTop:24, fontSize:11, color:'var(--text-tertiary)', fontFamily:'var(--font-mono)'}}>
              ADMIN_EMAILS = ['nyx@xmlforge.io'] • Rôle actuel: {user?.email} • Préparé pour futur système de rôles (ADMIN, USER) via user.roles
            </div>
          </div>
        </div>
      </div>
    )
  }

  return children
}
