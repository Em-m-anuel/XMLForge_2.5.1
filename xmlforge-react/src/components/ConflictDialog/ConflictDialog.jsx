import React from 'react'

export function ConflictDialog({ open, onReload, onClose }) {
  if (!open) return null
  return (
    <div className="modal-overlay open" onClick={onClose}>
      <div className="modal" onClick={event => event.stopPropagation()}>
        <div className="modal-head"><h3>Conflit de version</h3><button className="icon-btn" onClick={onClose}>✕</button></div>
        <div className="modal-body">
          <div className="danger-box"><b>Cette base a été modifiée depuis votre dernière synchronisation.</b><br/>Vos changements n'ont pas écrasé la version plus récente.</div>
          <p className="desc">Rechargez les données avant de recommencer, ou abandonnez vos modifications locales.</p>
        </div>
        <div className="modal-footer"><button className="btn" onClick={onClose}>Abandonner</button><button className="btn btn-primary" onClick={onReload}>Recharger la version récente</button></div>
      </div>
    </div>
  )
}
