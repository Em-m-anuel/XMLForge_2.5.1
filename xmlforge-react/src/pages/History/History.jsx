import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sidebar } from '../../components/Sidebar/Sidebar'
import { useToast } from '../../components/Toast/Toast'
import { historyService } from '../../services/historyService'

export function HistoryPage() {
  const navigate = useNavigate()
  const { notify } = useToast()
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [typeFilter, setTypeFilter] = useState('all')
  const [dbFilter, setDbFilter] = useState('')

  const fetchHistory = useCallback(async () => {
    setLoading(true)
    try {
      const data = await historyService.list(200, null)
      setHistory(data)
    } catch (err) {
      notify('error', 'Erreur', err.message)
    } finally {
      setLoading(false)
    }
  }, [notify])

  useEffect(() => { fetchHistory() }, [fetchHistory])

  const filtered = history.filter(h => {
    const typeOk = typeFilter === 'all' || (h.element_type && h.element_type.toLowerCase().includes(typeFilter.toLowerCase()))
    const dbOk = !dbFilter.trim() || (h.element_name && h.element_name.toLowerCase().includes(dbFilter.toLowerCase())) || (h.description && h.description.toLowerCase().includes(dbFilter.toLowerCase())) || (h.database_id && String(h.database_id).includes(dbFilter))
    return typeOk && dbOk
  })

  const groupByDate = () => {
    const groups = {}
    filtered.forEach(item => {
      const date = new Date(item.created_at || item.date || item.timestamp)
      const today = new Date()
      const yesterday = new Date()
      yesterday.setDate(today.getDate() - 1)
      let label = date.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })
      if (date.toDateString() === today.toDateString()) label = "Aujourd'hui"
      else if (date.toDateString() === yesterday.toDateString()) label = "Hier"
      if (!groups[label]) groups[label] = []
      groups[label].push(item)
    })
    return groups
  }

  const groups = groupByDate()

  return (
    <div className="screen active" id="screen-history">
      <aside className="sidebar">
        <Sidebar active="history" />
      </aside>
      <div className="dash-main">
        <div className="page-header">
          <a className="back-link" href="#" onClick={(e) => { e.preventDefault(); navigate('/dashboard') }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M19 12H5" /><path d="M12 19l-7-7 7-7" /></svg>
            Bases de données
          </a>
        </div>
        <div className="dash-content">
          <div className="dash-head">
            <div>
              <h1>Historique</h1>
              <p>Timeline des actions métier effectuées sur vos bases</p>
            </div>
            <div className="filters-bar">
              <select className="form-input" value={typeFilter} onChange={e => setTypeFilter(e.target.value)}>
                <option value="all">Tous les types</option>
                <option value="base">Base</option>
                <option value="table">Table</option>
                <option value="colonne">Colonne</option>
              </select>
              <input className="form-input" placeholder="Filtrer par base..." value={dbFilter} onChange={e => setDbFilter(e.target.value)} />
              <button className="btn btn-sm" onClick={() => { notify('info', 'Actualisé', 'L’historique a été rechargé.'); fetchHistory() }}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 2v6h-6" /><path d="M3 12a9 9 0 0 1 15-6.7L21 8" /><path d="M3 22v-6h6" /><path d="M21 12a9 9 0 0 1-15 6.7L3 16" /></svg>
                Actualiser
              </button>
            </div>
          </div>

          {loading ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {[...Array(5)].map((_, i) => (
                <div key={i} className="skeleton" style={{ height: '80px', borderRadius: '10px' }}></div>
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <div className="empty-state">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10" /><path d="M12 6v6l4 2" /></svg>
              <div className="es-title">Aucun événement</div>
              <div className="es-desc">Aucune entrée d'historique ne correspond aux filtres sélectionnés.</div>
            </div>
          ) : (
            <div>
              {Object.entries(groups).map(([label, items]) => (
                <div key={label}>
                  <div className="tl-group-label">{label}</div>
                  {items.map((h, idx) => {
                    const typeBadge = h.element_type === 'base' ? 'badge-blue' : h.element_type === 'table' ? 'badge-green' : h.element_type === 'colonne' ? 'badge-warn' : 'badge-gray'
                    const time = h.created_at ? new Date(h.created_at).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }) : ''
                    return (
                      <div key={h.id || idx} className="tl-card">
                        <div className="tl-dot-col"><span className="tl-dot"></span></div>
                        <div className="tl-body">
                          <div className="tl-head">
                            <span className="who">{h.user_name} {h.action_type} <b>{h.element_name}</b></span>
                            <span className={`badge ${typeBadge}`}>{h.element_type}</span>
                            <span className="time">{time}</span>
                          </div>
                          <div className="tl-desc">{h.description}</div>
                          <div className="tl-meta-row">
                            {h.database_id && <span className="badge badge-blue">DB {h.database_id}</span>}
                            {h.table_id && <span className="badge badge-gray">Table {h.table_id}</span>}
                            {h.ip_address && <span className="ip">IP {h.ip_address}</span>}
                          </div>
                          {(h.before || h.after) && (
                            <div className="tl-details">
                              before: {h.before ? (typeof h.before === 'string' ? h.before.slice(0, 200) : JSON.stringify(h.before).slice(0,200)) : 'null'} → after: {h.after ? (typeof h.after === 'string' ? h.after.slice(0,200) : JSON.stringify(h.after).slice(0,200)) : 'null'}
                            </div>
                          )}
                          {h.uuid && <div className="tl-footer">UUID {h.uuid}</div>}
                        </div>
                      </div>
                    )
                  })}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
