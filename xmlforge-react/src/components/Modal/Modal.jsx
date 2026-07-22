import { useEffect } from 'react'
import './Modal.css'
import { IconButton } from '../IconButton/IconButton'

export function Modal({ open, onClose, title, icon, children, footer, wide=false }){
  useEffect(()=>{
    if(!open) return
    const onEsc = (e)=>{ if(e.key==='Escape') onClose?.() }
    document.addEventListener('keydown', onEsc)
    return ()=> document.removeEventListener('keydown', onEsc)
  },[open,onClose])

  if(!open) return null

  return (
    <div className={`modal-overlay ${open ? 'open' : ''}`} onClick={(e)=>{ if(e.target===e.currentTarget) onClose?.() }}>
      <div className={`modal ${wide ? 'modal-wide' : ''}`} role="dialog" aria-modal="true">
        <div className="modal-head">
          <h3>{icon && <span className="modal-head-icon">{icon}</span>}{title}</h3>
          <IconButton onClick={onClose} aria-label="Fermer">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg>
          </IconButton>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>
  )
}
