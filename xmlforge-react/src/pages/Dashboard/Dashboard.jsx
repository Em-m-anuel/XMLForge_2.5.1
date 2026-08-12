import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sidebar } from '../../components/Sidebar/Sidebar'
import { useToast } from '../../components/Toast/Toast'
import { useAuth } from '../../context/AuthContext'
import { databaseService } from '../../services/databaseService'
import { importService } from '../../services/importService'
import { exportService } from '../../services/exportService'
import { projectService } from '../../services/projectService'
import { socketService } from '../../services/socketService'

export function Dashboard() {
  const navigate = useNavigate()
  const { notify } = useToast()
  const { user } = useAuth()

  const [databases, setDatabases] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [showImport, setShowImport] = useState(false)
  const [showImportProject, setShowImportProject] = useState(false)
  const [showNewDb, setShowNewDb] = useState(false)
  const [showEditDb, setShowEditDb] = useState(null)
  const [newDbName, setNewDbName] = useState('')
  const [newDbDesc, setNewDbDesc] = useState('')
  const [editDbName, setEditDbName] = useState('')
  const [editDbDesc, setEditDbDesc] = useState('')
  const [dragOver, setDragOver] = useState(false)
  const [importing, setImporting] = useState(false)
  const [openCtx, setOpenCtx] = useState(null)
  const fileInputRef = useRef(null)
  const projectFileRef = useRef(null)

  const fetchDatabases = useCallback(async () => {
    setLoading(true)
    try {
      const data = await databaseService.list(true)
      setDatabases(data)
    } catch (err) {
      notify('error', 'Erreur', err.message)
    } finally {
      setLoading(false)
    }
  }, [notify])

  useEffect(() => { fetchDatabases() }, [fetchDatabases])

  useEffect(() => {
    socketService.connect()
    const unsub = socketService.on('new_database', (payload) => {
      notify('info', 'Nouvelle base', `${payload.by} a créé ${payload.database?.name || 'une base'}`)
      fetchDatabases()
    })
    const unsub2 = socketService.on('modification', () => fetchDatabases())
    const unsub3 = socketService.on('suppression', () => fetchDatabases())
    return () => { unsub(); unsub2(); unsub3() }
  }, [fetchDatabases, notify])

  useEffect(() => {
    const handler = () => setOpenCtx(null)
    document.addEventListener('click', handler)
    return () => document.removeEventListener('click', handler)
  }, [])

  const filtered = databases.filter(d => d.name.toLowerCase().includes(search.trim().toLowerCase()))

  const handleCreateDb = async () => {
    if (!newDbName.trim()) { notify('error', 'Nom requis', ''); return }
    try {
      const db = await databaseService.create({ name: newDbName.trim(), description: newDbDesc.trim() })
      setDatabases(prev => [db, ...prev])
      setShowNewDb(false)
      setNewDbName(''); setNewDbDesc('')
      notify('success', 'Base créée', `« ${db.name} » créée`)
    } catch (err) {
      notify('error', 'Erreur création', err.message)
    }
  }

  const handleEditDbOpen = (db) => {
    if (db.status === 'ARCHIVED') { notify('error', 'Archivée', 'Restaurez d’abord'); return }
    setShowEditDb(db); setEditDbName(db.name); setEditDbDesc(db.description || '')
  }

  const handleSaveEditDb = async () => {
    if (!showEditDb) return
    try {
      const updated = await databaseService.update(showEditDb.id, { name: editDbName.trim(), description: editDbDesc.trim() })
      setDatabases(prev => prev.map(d => d.id === updated.id ? updated : d))
      setShowEditDb(null)
      notify('success', 'Base mise à jour', `« ${updated.name} » modifiée`)
    } catch (err) { notify('error', 'Erreur', err.message) }
  }

  const handleArchiveToggle = async (db) => {
    try {
      const res = db.status === 'ARCHIVED' ? await databaseService.restore(db.id) : await databaseService.archive(db.id)
      setDatabases(prev => prev.map(d => d.id === res.id ? res : d))
      notify(res.status === 'ARCHIVED' ? 'info' : 'success', res.status === 'ARCHIVED' ? 'Archivée' : 'Restaurée', `« ${db.name} » ${res.status === 'ARCHIVED' ? 'archivée' : 'active'}`)
    } catch (err) { notify('error', 'Erreur', err.message) }
  }

  const handleDeleteDb = async (db) => {
    if (!window.confirm(`Supprimer définitivement « ${db.name} » ?`)) return
    try {
      await databaseService.delete(db.id)
      setDatabases(prev => prev.filter(d => d.id !== db.id))
      notify('error', 'Supprimée', `« ${db.name} » supprimée`)
    } catch (err) { notify('error', 'Erreur', err.message) }
  }

  const handleDuplicate = async (db) => {
    try {
      const { xml } = await exportService.exportXml(db.id)
      await importService.importXmlRaw(xml, `${db.name} (copie)`)
      await fetchDatabases()
      notify('success', 'Dupliquée', `Copie de « ${db.name} » créée`)
    } catch (err) { notify('error', 'Erreur', err.message) }
  }

  const handleExportProject = async (db) => {
    try {
      await projectService.exportProject(db.id, { download: true })
      notify('success', 'Projet exporté', `Projet complet « ${db.name} » avec données, protections, file_identifier`)
    } catch (err) { notify('error', 'Erreur export projet', err.message) }
  }

  const handleImportFile = async (file) => {
    if (!file) return
    setImporting(true)
    try {
      await importService.importXml(file)
      await fetchDatabases()
      setShowImport(false)
      notify('success', 'Import XML', 'Nouvelle base créée')
    } catch (err) { notify('error', 'Erreur import', err.message) } finally { setImporting(false) }
  }

  const handleImportProjectFile = async (file) => {
    if (!file) return
    setImporting(true)
    try {
      const db = await projectService.importProject(file)
      await fetchDatabases()
      setShowImportProject(false)
      notify('success', 'Projet importé', `Base « ${db.name} » reconstruite avec tables, colonnes, données`)
    } catch (err) { notify('error', 'Erreur import projet', err.message) } finally { setImporting(false) }
  }

  const onDrop = (e, project=false) => {
    e.preventDefault(); setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) project ? handleImportProjectFile(file) : handleImportFile(file)
  }

  const initials = user?.full_name ? user.full_name.slice(0,2).toUpperCase() : 'NX'

  return (
    <div className="screen active" id="screen-dashboard">
      <aside className="sidebar"><Sidebar active="databases" /></aside>
      <div className="dash-main">
        <div className="topbar">
          <div className="topbar-search">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
            <input type="text" placeholder="Rechercher une base..." value={search} onChange={e => setSearch(e.target.value)} />
          </div>
          <div className="topbar-right">
            <span className="badge badge-green"><span className="badge-dot" style={{ background: '#22C55E' }}></span>Connecté</span>
            <div className="avatar">{initials}</div>
          </div>
        </div>

        <div className="dash-content">
          <div className="dash-head">
            <div>
              <h1>Mes bases de données</h1>
              <p>{databases.length} bases · synchro {loading ? 'en cours...' : 'à l’instant'}</p>
            </div>
            <div className="dash-actions">
              <button className="btn" onClick={() => setShowImportProject(true)}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M12 18v-6M9 15l3 3 3-3"/></svg>
                Importer projet
              </button>
              <button className="btn" onClick={() => setShowImport(true)}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/></svg>
                Importer XML
              </button>
              <button className="btn btn-primary" onClick={() => setShowNewDb(true)}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 5v14M5 12h14"/></svg>
                Nouvelle base
              </button>
            </div>
          </div>

          {loading ? (
            <div className="db-grid">{[...Array(6)].map((_, i) => <div key={i} className="db-card" style={{ minHeight: '160px' }}><div className="skeleton" style={{ height: '100%' }}></div></div>)}</div>
          ) : filtered.length === 0 ? (
            <div className="empty-state"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg><div className="es-title">{search ? 'Aucun résultat' : 'Aucune base'}</div><div className="es-desc">{search ? 'Aucune base ne correspond' : 'Créez votre première base'}</div></div>
          ) : (
            <div className="db-grid">
              {filtered.map((d, i) => {
                const archived = d.status === 'ARCHIVED'
                return (
                  <div key={d.id} className={`db-card ${archived ? 'archived' : ''}`} style={{ animationDelay: `${i*0.05}s` }}>
                    <div className="db-card-top">
                      <div className="db-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg></div>
                      <div className="ctx-btn">
                        <button className="icon-btn" onClick={(e) => { e.stopPropagation(); setOpenCtx(openCtx === d.id ? null : d.id) }}>
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="5" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="12" cy="19" r="1.5"/></svg>
                        </button>
                        <div className={`ctx-menu ${openCtx === d.id ? 'open' : ''}`}>
                          <button disabled={archived} onClick={(e) => { e.stopPropagation(); setOpenCtx(null); handleEditDbOpen(d) }}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg>Modifier</button>
                          <button onClick={(e) => { e.stopPropagation(); setOpenCtx(null); handleDuplicate(d) }}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>Dupliquer</button>
                          <button onClick={(e) => { e.stopPropagation(); setOpenCtx(null); handleExportProject(d) }}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/></svg>Exporter projet complet</button>
                          <hr />
                          <button onClick={(e) => { e.stopPropagation(); setOpenCtx(null); handleArchiveToggle(d) }}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="4" width="18" height="4" rx="1"/><path d="M5 8v11a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8"/><path d="M10 12h4"/></svg>{archived ? 'Restaurer' : 'Archiver'}</button>
                          <hr />
                          <button className="danger" onClick={(e) => { e.stopPropagation(); setOpenCtx(null); handleDeleteDb(d) }}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0-1 14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2L4 6"/></svg>Supprimer</button>
                        </div>
                      </div>
                    </div>
                    <h3>{d.name}</h3>
                    <p className="desc">{d.description || 'Aucune description'}</p>
                    <div className="meta"><span>{d.tables_count || 0} tables</span><span className="dim">·</span><span>{d.creator_name || '—'}</span></div>
                    <div className="meta"><span className="dim">Modifié {d.updated_at ? new Date(d.updated_at).toLocaleDateString() : '—'}</span></div>
                    <div className="db-card-footer">
                      <div className="db-card-badges"><span className={`badge ${archived ? 'badge-gray' : 'badge-green'}`}><span className="badge-dot" style={{ background: archived ? '#A0AEC0' : '#22C55E' }}></span>{archived ? 'ARCHIVÉ' : 'ACTIF'}</span></div>
                      <a className="db-card-open" href="#" onClick={(e) => { e.preventDefault(); if (archived) { notify('error', 'Archivée', 'Restaurez'); return } navigate(`/workspace/${encodeURIComponent(d.name)}?dbId=${d.id}`) }}>Ouvrir <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg></a>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>

      {/* Import XML */}
      <div className={`modal-overlay ${showImport ? 'open' : ''}`} onClick={() => setShowImport(false)}>
        <div className="modal" onClick={e => e.stopPropagation()}>
          <div className="modal-head"><h3>Importer XML</h3><button className="icon-btn" onClick={() => setShowImport(false)}>✕</button></div>
          <div className="modal-body">
            <p className="desc">Import simple : crée une nouvelle base à partir d'un XML structure.</p>
            <div className={`dropzone ${dragOver ? 'dragover' : ''}`} onDragEnter={e => { e.preventDefault(); setDragOver(true) }} onDragOver={e => { e.preventDefault(); setDragOver(true) }} onDragLeave={e => { e.preventDefault(); setDragOver(false) }} onDrop={e => onDrop(e,false)} onClick={() => fileInputRef.current?.click()}>
              <div><b>Cliquer</b> ou glisser .xml</div>
            </div>
            <input type="file" ref={fileInputRef} className="hidden" accept=".xml" onChange={e => handleImportFile(e.target.files[0])} />
            {importing && <div className="import-progress"><span className="mini-spinner"></span>Import...</div>}
          </div>
          <div className="modal-footer"><button className="btn" onClick={() => setShowImport(false)}>Annuler</button><button className="btn btn-primary" onClick={() => fileInputRef.current?.click()}>Importer</button></div>
        </div>
      </div>

      {/* Import Project */}
      <div className={`modal-overlay ${showImportProject ? 'open' : ''}`} onClick={() => setShowImportProject(false)}>
        <div className="modal" onClick={e => e.stopPropagation()}>
          <div className="modal-head"><h3>Importer projet complet</h3><button className="icon-btn" onClick={() => setShowImportProject(false)}>✕</button></div>
          <div className="modal-body">
            <p className="desc">Import projet : reconstruit base + tables + colonnes + protections + file_identifier + <b>données</b>. Un seul fichier suffit.</p>
            <div className={`dropzone ${dragOver ? 'dragover' : ''}`} onDragEnter={e => { e.preventDefault(); setDragOver(true) }} onDragOver={e => { e.preventDefault(); setDragOver(true) }} onDragLeave={e => { e.preventDefault(); setDragOver(false) }} onDrop={e => onDrop(e,true)} onClick={() => projectFileRef.current?.click()}>
              <div><b>Projet complet</b> avec données, protections</div>
            </div>
            <input type="file" ref={projectFileRef} className="hidden" accept=".xml" onChange={e => handleImportProjectFile(e.target.files[0])} />
            {importing && <div className="import-progress"><span className="mini-spinner"></span>Import projet...</div>}
          </div>
          <div className="modal-footer"><button className="btn" onClick={() => setShowImportProject(false)}>Annuler</button><button className="btn btn-primary" onClick={() => projectFileRef.current?.click()}>Importer projet</button></div>
        </div>
      </div>

      {/* New DB */}
      <div className={`modal-overlay ${showNewDb ? 'open' : ''}`} onClick={() => setShowNewDb(false)}>
        <div className="modal" onClick={e => e.stopPropagation()}>
          <div className="modal-head"><h3>Nouvelle base</h3><button className="icon-btn" onClick={() => setShowNewDb(false)}>✕</button></div>
          <div className="modal-body">
            <div className="field-block"><label className="form-label">Nom</label><input className="form-input" value={newDbName} onChange={e => setNewDbName(e.target.value)} placeholder="Bibliothèque..." /></div>
            <div className="field-block"><label className="form-label">Description</label><input className="form-input" value={newDbDesc} onChange={e => setNewDbDesc(e.target.value)} placeholder="Description" /></div>
          </div>
          <div className="modal-footer"><button className="btn" onClick={() => setShowNewDb(false)}>Annuler</button><button className="btn btn-primary" onClick={handleCreateDb}>Créer</button></div>
        </div>
      </div>

      {/* Edit DB */}
      <div className={`modal-overlay ${showEditDb ? 'open' : ''}`} onClick={() => setShowEditDb(null)}>
        <div className="modal" onClick={e => e.stopPropagation()}>
          <div className="modal-head"><h3>Modifier base</h3><button className="icon-btn" onClick={() => setShowEditDb(null)}>✕</button></div>
          <div className="modal-body">
            <div className="field-block"><label className="form-label">Nom</label><input className="form-input" value={editDbName} onChange={e => setEditDbName(e.target.value)} /></div>
            <div className="field-block"><label className="form-label">Description</label><input className="form-input" value={editDbDesc} onChange={e => setEditDbDesc(e.target.value)} /></div>
          </div>
          <div className="modal-footer"><button className="btn" onClick={() => setShowEditDb(null)}>Annuler</button><button className="btn btn-primary" onClick={handleSaveEditDb}>Enregistrer</button></div>
        </div>
      </div>
    </div>
  )
}
