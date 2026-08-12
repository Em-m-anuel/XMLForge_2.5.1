import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sidebar } from '../../components/Sidebar/Sidebar'
import { useToast } from '../../components/Toast/Toast'
import { auditService } from '../../services/auditService'

export function AuditPage() {
  const navigate = useNavigate()
  const { notify } = useToast()
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')

  const fetchAudit = useCallback(async () => {
    setLoading(true)
    try {
      const data = await auditService.list(200)
      setLogs(data)
    } catch (err) {
      notify('error', 'Erreur', err.message)
    } finally {
      setLoading(false)
    }
  }, [notify])

  useEffect(() => { fetchAudit() }, [fetchAudit])

  const filtered = logs.filter(a => filter === 'all' || (a.action && a.action.toUpperCase().includes(filter.toUpperCase())))

  const badgeColor = (action) => {
    if (!action) return 'badge-gray'
    if (action.startsWith('SUPPRESSION') || action === 'ERREUR' || action.includes('ERREUR')) return 'badge-red'
    if (action.startsWith('CONVERSION')) return 'badge-blue'
    if (action === 'DECONNEXION') return 'badge-gray'
    return 'badge-green'
  }

  return (
    <div className="screen active" id="screen-audit">
      <aside className="sidebar">
        <Sidebar active="audit" />
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
              <h1>Audit</h1>
              <p>Journal indépendant de toutes les actions du système</p>
            </div>
            <div className="filters-bar">
              <select className="form-input" value={filter} onChange={e => setFilter(e.target.value)}>
                <option value="all">Toutes les actions</option>
                <option value="CONNEXION">Connexion</option>
                <option value="CREATION">Création</option>
                <option value="SUPPRESSION">Suppression</option>
                <option value="IMPORT">Import</option>
                <option value="EXPORT">Export</option>
                <option value="CONVERSION">Conversion</option>
                <option value="ERREUR">Erreur</option>
              </select>
              <button className="btn btn-sm" onClick={() => { notify('info', 'Actualisé', 'Le journal d’audit a été rechargé.'); fetchAudit() }}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 2v6h-6" /><path d="M3 12a9 9 0 0 1 15-6.7L21 8" /><path d="M3 22v-6h6" /><path d="M21 12a9 9 0 0 1-15 6.7L3 16" /></svg>
                Actualiser
              </button>
            </div>
          </div>
          <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', overflow: 'auto', background: 'var(--card)' }}>
            <table className="audit-table">
              <thead><tr><th>Date</th><th>Utilisateur</th><th>Action</th><th>Élément</th><th>Description</th><th>IP</th></tr></thead>
              <tbody>
                {loading ? (
                  [...Array(6)].map((_, i) => (
                    <tr key={i}><td colSpan={6}><div className="skeleton" style={{ height: '20px' }}></div></td></tr>
                  ))
                ) : filtered.length === 0 ? (
                  <tr><td colSpan={6}><div className="empty-state"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z" /></svg><div className="es-title">Aucun log</div><div className="es-desc">Aucune entrée ne correspond à ce filtre.</div></div></td></tr>
                ) : (
                  filtered.map((a, idx) => (
                    <tr key={a.id || idx}>
                      <td className="date-cell">{a.timestamp ? new Date(a.timestamp).toLocaleString('fr-FR') : a.created_at ? new Date(a.created_at).toLocaleString('fr-FR') : '—'}</td>
                      <td>{a.user_name || '—'}</td>
                      <td><span className={`badge ${badgeColor(a.action)}`}>{a.action}</span></td>
                      <td>{a.element_name || a.element_type || '—'}</td>
                      <td style={{ color: 'var(--text-secondary)' }}>{a.description || '—'}</td>
                      <td className="ip-cell">{a.ip_address || '—'}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
