import { createContext, useContext, useState, useCallback } from 'react'

const ToastContext = createContext(null)

const icons = {
  check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>',
  error: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg>',
  info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>',
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const notify = useCallback((type, title, msg) => {
    const id = Date.now() + Math.random()
    setToasts(t => [...t, { id, type, title, msg, out: false }])
    setTimeout(() => {
      setToasts(t => t.map(x => x.id === id ? { ...x, out: true } : x))
      setTimeout(() => {
        setToasts(t => t.filter(x => x.id !== id))
      }, 260)
    }, 3400)
  }, [])

  return (
    <ToastContext.Provider value={{ notify }}>
      {children}
      <div className="toast-stack" id="toast-stack">
        {toasts.map(toast => (
          <div key={toast.id} className={`toast ${toast.type} ${toast.out ? 'out' : ''}`}>
            <div className="ic" dangerouslySetInnerHTML={{ __html: icons[toast.type] || icons.info }} />
            <div className="txt"><b>{toast.title}</b><span>{toast.msg}</span></div>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}
