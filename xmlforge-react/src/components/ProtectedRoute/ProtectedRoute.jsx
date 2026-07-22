import { Navigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { Loader } from '../Loader/Loader'

export function ProtectedRoute({ children }){
  const { isAuthenticated, loading } = useAuth()

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

  return children
}
