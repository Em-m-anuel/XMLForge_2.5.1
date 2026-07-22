import { useState, useRef, useEffect } from 'react'
import { IconButton } from '../IconButton/IconButton'
import './ContextMenu.css'

export function ContextMenu({ trigger, children }){
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(()=>{
    const outside = (e)=>{
      if(ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('click', outside)
    return ()=> document.removeEventListener('click', outside)
  },[])

  return (
    <div className="ctx-btn" ref={ref}>
      <div onClick={(e)=>{ e.stopPropagation(); setOpen(o=>!o) }}>
        {trigger}
      </div>
      <div className={`ctx-menu ${open ? 'open' : ''}`}>
        {children}
      </div>
    </div>
  )
}
