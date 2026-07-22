import { Suspense, lazy } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { ToastProvider } from './components/Toast/Toast'
import { AuthProvider } from './context/AuthContext'
import { DatabaseProvider } from './context/DatabaseContext'
import { ProtectedRoute } from './components/ProtectedRoute/ProtectedRoute'
import { AdminRoute } from './components/AdminRoute/AdminRoute'
import { Loader } from './components/Loader/Loader'

// Lazy loading for code splitting
const Login = lazy(()=> import('./pages/Login/Login').then(m=>({ default: m.Login })))
const Register = lazy(()=> import('./pages/Register/Register').then(m=>({ default: m.Register })))
const Dashboard = lazy(()=> import('./pages/Dashboard/Dashboard').then(m=>({ default: m.Dashboard })))
const Workspace = lazy(()=> import('./pages/Workspace/Workspace').then(m=>({ default: m.Workspace })))
const HistoryPage = lazy(()=> import('./pages/History/History').then(m=>({ default: m.HistoryPage })))
const AuditPage = lazy(()=> import('./pages/Audit/Audit').then(m=>({ default: m.AuditPage })))

function AppFallback(){
  return (
    <div style={{height:'100vh', display:'flex', alignItems:'center', justifyContent:'center', background:'var(--bg)', color:'var(--text)'}}>
      <Loader size={32} />
    </div>
  )
}

function App(){
  return (
    <ToastProvider>
      <AuthProvider>
        <DatabaseProvider>
          <Suspense fallback={<AppFallback />}>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
              <Route path="/workspace/:dbName" element={<ProtectedRoute><Workspace /></ProtectedRoute>} />
              <Route path="/history" element={<ProtectedRoute><AdminRoute><HistoryPage /></AdminRoute></ProtectedRoute>} />
              <Route path="/audit" element={<ProtectedRoute><AdminRoute><AuditPage /></AdminRoute></ProtectedRoute>} />
              <Route path="/" element={<Navigate to="/login" replace />} />
              <Route path="*" element={<Navigate to="/login" replace />} />
            </Routes>
          </Suspense>
        </DatabaseProvider>
      </AuthProvider>
    </ToastProvider>
  )
}

export default App
