import { createContext, useContext, useState, useCallback } from 'react'
import './Toast.css'

const ToastContext = createContext(null)

const icons = {
  success: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5"/></svg>,
  error: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg>,
  info: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>,
}

export function ToastProvider({ children }){
  const [toasts, setToasts] = useState([])

  const notify = useCallback((type='info', title='', message='')=>{
    const id = Date.now() + Math.random()
    setToasts(s=>[...s, { id, type, title, message }])
    setTimeout(()=> setToasts(s=> s.filter(t=>t.id!==id)), 3400)
  },[])

  const remove = useCallback((id)=>{
    setToasts(s=> s.filter(t=>t.id!==id))
  },[])

  return (
    <ToastContext.Provider value={{ notify }}>
      {children}
      <div className="toast-stack">
        {toasts.map(t=>(
          <div key={t.id} className={`toast ${t.type}`} onClick={()=>remove(t.id)}>
            <div className="ic">{icons[t.type]}</div>
            <div className="txt"><b>{t.title}</b><span>{t.message}</span></div>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast(){
  const ctx = useContext(ToastContext)
  if(!ctx) throw new Error('useToast must be inside ToastProvider')
  return ctx
}
