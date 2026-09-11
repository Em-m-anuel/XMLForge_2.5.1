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
import { accessService, accessLevel } from '../../services/accessService'
import { ConflictDialog } from '../../components/ConflictDialog/ConflictDialog'

export function Dashboard() {
  const navigate = useNavigate()
  const { notify } = useToast()
  const { user } = useAuth()

  const [databases, setDatabases] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [scopeFilter, setScopeFilter] = useState('all')
  const [showImport, setShowImport] = useState(false)
  const [importKind, setImportKind] = useState('xml') // 'xml' | 'sql' | 'project'
  const [showExportFull, setShowExportFull] = useState(false)
  const [exportTarget, setExportTarget] = useState(null)
  const [showNewDb, setShowNewDb] = useState(false)
  const [showEditDb, setShowEditDb] = useState(null)
  const [newDbName, setNewDbName] = useState('')
  const [newDbDesc, setNewDbDesc] = useState('')
  const [newDbScope, setNewDbScope] = useState('PERSONAL')
  const [newDbCommonPermission, setNewDbCommonPermission] = useState('VIEW')
  const [editDbName, setEditDbName] = useState('')
  const [editDbDesc, setEditDbDesc] = useState('')
  const [editDbScope, setEditDbScope] = useState('PERSONAL')
  const [editDbCommonPermission, setEditDbCommonPermission] = useState('VIEW')
  const [showAccess, setShowAccess] = useState(null)
  const [permissions, setPermissions] = useState([])
  const [accessEmail, setAccessEmail] = useState('')
  const [grantLevel, setGrantLevel] = useState('VIEW')
  const [accessLoading, setAccessLoading] = useState(false)
  const [conflict, setConflict] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [importing, setImporting] = useState(false)
  const [openCtx, setOpenCtx] = useState(null)
  const fileInputRef = useRef(null)

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

  const filtered = databases.filter(database => {
    const matchesSearch = database.name.toLowerCase().includes(search.trim().toLowerCase())
    const matchesScope = scopeFilter === 'all' || database.scope === scopeFilter
    return matchesSearch && matchesScope
  })

  const handleCreateDb = async () => {
    if (!newDbName.trim()) { notify('error', 'Nom requis', ''); return }
    try {
      const db = await databaseService.create({
        name: newDbName.trim(), description: newDbDesc.trim(), scope: newDbScope,
        common_permission: newDbScope === 'COMMON' ? newDbCommonPermission : null,
      })
      setDatabases(prev => [db, ...prev])
      setShowNewDb(false)
      setNewDbName(''); setNewDbDesc(''); setNewDbScope('PERSONAL'); setNewDbCommonPermission('VIEW')
      notify('success', 'Base créée', `« ${db.name} » créée`)
    } catch (err) {
      notify('error', 'Erreur création', err.message)
    }
  }

  const handleEditDbOpen = (db) => {
    if (db.status === 'ARCHIVED') { notify('error', 'Archivée', 'Restaurez d’abord'); return }
    setShowEditDb(db); setEditDbName(db.name); setEditDbDesc(db.description || '')
    setEditDbScope(db.scope || 'PERSONAL')
    setEditDbCommonPermission(db.common_permission || 'VIEW')
  }

  const handleSaveEditDb = async () => {
    if (!showEditDb) return
    try {
      // Le backend exige can_admin dès que la clé "scope" est présente.
      // Un utilisateur EDIT peut renommer/décrire, mais pas changer la portée.
      const payload = { name: editDbName.trim(), description: editDbDesc.trim() }
      if (showEditDb.access?.can_admin) {
        payload.scope = editDbScope
        if (editDbScope === 'COMMON') payload.common_permission = editDbCommonPermission
      }
      const updated = await databaseService.update(showEditDb.id, payload, showEditDb.document_version)
      setDatabases(prev => prev.map(d => d.id === updated.id ? updated : d))
      setShowEditDb(null)
      notify('success', 'Base mise à jour', `« ${updated.name} » modifiée`)
    } catch (err) {
      if (err.isConflict) setConflict(true)
      else notify('error', 'Erreur', err.message)
    }
  }

  const handleArchiveToggle = async (db) => {
    try {
      const res = db.status === 'ARCHIVED' ? await databaseService.restore(db.id) : await databaseService.archive(db.id)
      setDatabases(prev => prev.map(d => d.id === res.id ? { ...res, access: d.access, is_owner: d.is_owner } : d))
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
      // L'identifiant de base XML doit respecter ^[A-Za-z_][A-Za-z0-9_]*$
      const base = String(db.name || 'base').replace(/[^A-Za-z0-9_]/g, '_').replace(/^[^A-Za-z_]/, '_')
      await importService.importXmlRaw(xml, `${base}_copie`)
      await fetchDatabases()
      notify('success', 'Dupliquée', `Copie de « ${db.name} » créée`)
    } catch (err) { notify('error', 'Erreur', err.message) }
  }

  const handleExportProject = async (db) => {
    if (!db) { notify('error', 'Base requise', 'Sélectionnez une base administrable.'); return }
    try {
      await projectService.exportProject(db.id, { download: true, name: db.name })
      setShowExportFull(false)
      notify('success', 'Export complet généré', `« ${db.name} » contient structure, données, relations et métadonnées.`)
    } catch (err) { notify('error', 'Erreur export complet', err.message) }
  }

  const handleImportFile = async (file) => {
    if (!file) return
    setImporting(true)
    try {
      if (importKind === 'sql') await importService.importSql(file)
      else if (importKind === 'project') await projectService.importProject(file)
      else await importService.importXml(file)
      await fetchDatabases()
      setShowImport(false)
      notify('success', 'Import réussi', 'Nouvelle base créée depuis le fichier')
    } catch (err) { notify('error', 'Erreur import', err.message) } finally { setImporting(false) }
  }

  const onDrop = (e) => {
    e.preventDefault(); setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) handleImportFile(file)
  }

  const openAccess = async (database) => {
    setShowAccess(database)
    setAccessEmail('')
    setGrantLevel('VIEW')
    setAccessLoading(true)
    try {
      setPermissions(await accessService.listDatabase(database.id))
    } catch (err) {
      notify('error', 'Accès', err.message)
      setShowAccess(null)
    } finally {
      setAccessLoading(false)
    }
  }

  const grantAccess = async () => {
    if (!showAccess || !accessEmail.trim()) return
    const rights = grantLevel === 'MANAGE'
      ? { can_read: true, can_write: true, can_ddl: true, can_admin: true }
      : grantLevel === 'EDIT'
        ? { can_read: true, can_write: true, can_ddl: true, can_admin: false }
        : { can_read: true, can_write: false, can_ddl: false, can_admin: false }
    try {
      await accessService.grantDatabase(showAccess.id, { email: accessEmail.trim(), ...rights })
      setPermissions(await accessService.listDatabase(showAccess.id))
      setAccessEmail('')
      notify('success', 'Accès partagé', `${grantLevel} accordé`)
    } catch (err) { notify('error', 'Partage impossible', err.message) }
  }

  const revokeAccess = async (permission) => {
    try {
      await accessService.revokeDatabase(showAccess.id, permission.user_id)
      setPermissions(prev => prev.filter(item => item.user_id !== permission.user_id))
    } catch (err) { notify('error', 'Retrait impossible', err.message) }
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
              <p>{filtered.length} base{filtered.length > 1 ? 's' : ''} de données{scopeFilter === 'PERSONAL' ? ' personnelles' : scopeFilter === 'COMMON' ? ' communes' : ''} · synchronisées avec XMLForge</p>
            </div>
            <div className="dash-actions">
              <button className="btn" onClick={() => { setImportKind('xml'); setShowImport(true) }}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/></svg>
                Importer
              </button>
              <button className="btn" onClick={() => { setExportTarget(null); setShowExportFull(true) }}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7"/><path d="M16 6l-4-4-4 4"/><path d="M12 2v14"/></svg>
                Export complet
              </button>
              <button className="btn btn-primary" onClick={() => setShowNewDb(true)}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 5v14M5 12h14"/></svg>
                Nouvelle base
              </button>
            </div>
          </div>

          <div className="tabs-seg" id="db-scope-tabs" style={{ marginBottom: 18 }}>
            <button className={`tab-btn ${scopeFilter === 'all' ? 'active' : ''}`} onClick={() => setScopeFilter('all')}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>Toutes</button>
            <button className={`tab-btn ${scopeFilter === 'PERSONAL' ? 'active' : ''}`} onClick={() => setScopeFilter('PERSONAL')}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>Personnelles</button>
            <button className={`tab-btn ${scopeFilter === 'COMMON' ? 'active' : ''}`} onClick={() => setScopeFilter('COMMON')}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></svg>Communes</button>
          </div>

          {loading ? (
            <div className="db-grid">{[...Array(6)].map((_, i) => <div key={i} className="db-card" style={{ minHeight: '160px' }}><div className="skeleton" style={{ height: '100%' }}></div></div>)}</div>
          ) : filtered.length === 0 ? (
            <div className="empty-state"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg><div className="es-title">{search ? 'Aucun résultat' : 'Aucune base'}</div><div className="es-desc">{search ? 'Aucune base ne correspond' : 'Créez votre première base'}</div></div>
          ) : (
            <div className="db-grid">
              {filtered.map((d, i) => {
                const archived = d.status === 'ARCHIVED'
                const level = accessLevel(d)
                const canManage = Boolean(d.access?.can_admin)
                const canWrite = Boolean(d.access?.can_write)
                return (
                  <div key={d.id} className={`db-card ${archived ? 'archived' : ''}`} style={{ animationDelay: `${i*0.05}s` }}>
                    <div className="db-card-top">
                      <div className="db-card-icon">{d.scope === 'COMMON' ? <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></svg> : <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>}</div>
                      <div className="ctx-btn">
                        <button className="icon-btn" onClick={(e) => { e.stopPropagation(); setOpenCtx(openCtx === d.id ? null : d.id) }}>
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="5" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="12" cy="19" r="1.5"/></svg>
                        </button>
                        <div className={`ctx-menu ${openCtx === d.id ? 'open' : ''}`}>
                          {canWrite && <button disabled={archived} onClick={(e) => { e.stopPropagation(); setOpenCtx(null); handleEditDbOpen(d) }}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg>Modifier</button>}
                          {canManage && <button onClick={(e) => { e.stopPropagation(); setOpenCtx(null); handleDuplicate(d) }}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2 2h9a2 2 0 0 1 2 2v1"/></svg>Dupliquer</button>}
                          {canManage && <button onClick={(e) => { e.stopPropagation(); setOpenCtx(null); setExportTarget(d); setShowExportFull(true) }}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7"/><path d="M16 6l-4-4-4 4"/><path d="M12 2v14"/></svg>Export complet XMLForge</button>}
                          {canManage && <button onClick={(e) => { e.stopPropagation(); setOpenCtx(null); openAccess(d) }}>Gérer les accès</button>}
                          {canManage && <hr />}
                          {canManage && <button onClick={(e) => { e.stopPropagation(); setOpenCtx(null); handleArchiveToggle(d) }}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="4" width="18" height="4" rx="1"/><path d="M5 8v11a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8"/><path d="M10 12h4"/></svg>{archived ? 'Restaurer' : 'Archiver'}</button>}
                          {canManage && <hr />}
                          {canManage && <button className="danger" onClick={(e) => { e.stopPropagation(); setOpenCtx(null); handleDeleteDb(d) }}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0-1 14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2L4 6"/></svg>Supprimer</button>}
                        </div>
                      </div>
                    </div>
                    <h3>{d.name}</h3>
                    <p className="desc">{d.description || 'Aucune description'}</p>
                    <div className="meta"><span>{d.tables_count || 0} tables</span><span className="dim">·</span><span>Propriétaire : {d.owner_name || d.creator_name || '—'}</span></div>
                    <div className="meta"><span className="dim">Modifié {d.updated_at ? new Date(d.updated_at).toLocaleDateString() : '—'} · accès {level}</span></div>
                    <div className="db-card-footer">
                      <div className="db-card-badges">
                        <span className={`badge ${archived ? 'badge-gray' : 'badge-green'}`}><span className="badge-dot" style={{ background: archived ? '#A0AEC0' : '#22C55E' }}></span>{archived ? 'ARCHIVÉ' : 'ACTIF'}</span>
                        <span className={`badge ${d.scope === 'COMMON' ? 'badge-warn' : 'badge-blue'}`}>{d.scope === 'COMMON' ? 'Commune' : 'Personnelle'}</span>
                      </div>
                      <a className="db-card-open" href="#" onClick={(e) => { e.preventDefault(); if (archived) { notify('error', 'Archivée', 'Restaurez'); return } navigate(`/database/${d.id}`) }}>Ouvrir <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg></a>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>

      {/* Import XML / SQL / Projet */}
      <div className={`modal-overlay ${showImport ? 'open' : ''}`} onClick={() => setShowImport(false)}>
        <div className="modal" onClick={e => e.stopPropagation()}>
          <div className="modal-head"><h3>Importer une base</h3><button className="icon-btn" onClick={() => setShowImport(false)}>✕</button></div>
          <div className="modal-body">
            <div className="tabs-seg" style={{ marginBottom: 16 }}>
              <button className={`tab-btn ${importKind === 'xml' ? 'active' : ''}`} onClick={() => setImportKind('xml')}>XML (structure)</button>
              <button className={`tab-btn ${importKind === 'sql' ? 'active' : ''}`} onClick={() => setImportKind('sql')}>SQL (script)</button>
              <button className={`tab-btn ${importKind === 'project' ? 'active' : ''}`} onClick={() => setImportKind('project')}>Projet XMLForge</button>
            </div>
            <p className="desc">
              {importKind === 'xml' && 'Analyse un fichier XMLForge décrivant tables, colonnes et données. La base est créée avec le nom du document.'}
              {importKind === 'sql' && 'Convertit un script SQL (CREATE TABLE + INSERT) en XML puis crée la base. Limitations du parseur SQL documentées.'}
              {importKind === 'project' && 'Importe un export complet XMLForge (structure + données + métadonnées). Nécessite un export projet généré par XMLForge.'}
            </p>
            <div className={`dropzone ${dragOver ? 'dragover' : ''}`} onDragEnter={e => { e.preventDefault(); setDragOver(true) }} onDragOver={e => { e.preventDefault(); setDragOver(true) }} onDragLeave={e => { e.preventDefault(); setDragOver(false) }} onDrop={onDrop} onClick={() => fileInputRef.current?.click()}>
              <div><b>Cliquer</b> ou glisser {importKind === 'sql' ? '.sql' : '.xml'}</div>
            </div>
            <input type="file" ref={fileInputRef} className="hidden" accept={importKind === 'sql' ? '.sql' : '.xml'} onChange={e => handleImportFile(e.target.files[0])} />
            {importing && <div className="import-progress"><span className="mini-spinner"></span>Import...</div>}
          </div>
          <div className="modal-footer"><button className="btn" onClick={() => setShowImport(false)}>Annuler</button><button className="btn btn-primary" onClick={() => fileInputRef.current?.click()}>Importer</button></div>
        </div>
      </div>

      {/* New DB */}
      <div className={`modal-overlay ${showNewDb ? 'open' : ''}`} onClick={() => setShowNewDb(false)}>
        <div className="modal" onClick={e => e.stopPropagation()}>
          <div className="modal-head"><h3>Nouvelle base de données</h3><button className="icon-btn" onClick={() => setShowNewDb(false)}>✕</button></div>
          <div className="modal-body">
            <div className="field-block"><label className="form-label">Nom de la base</label><input className="form-input" value={newDbName} onChange={e => setNewDbName(e.target.value)} placeholder="Bibliothèque..." /></div>
            <div className="field-block"><label className="form-label">Description</label><input className="form-input" value={newDbDesc} onChange={e => setNewDbDesc(e.target.value)} placeholder="Description" /></div>
            <div className="field-block"><label className="form-label">Visibilité</label><select className="form-input" value={newDbScope} onChange={e => setNewDbScope(e.target.value)}><option value="PERSONAL">Personnelle — visible par vous uniquement</option><option value="COMMON">Commune — accessible à tous les utilisateurs actifs</option></select></div>
            {newDbScope === 'COMMON' && (
              <div className="field-block"><label className="form-label">Niveau collectif</label><select className="form-input" value={newDbCommonPermission} onChange={e => setNewDbCommonPermission(e.target.value)}><option value="VIEW">VIEW — lecture pour tous</option><option value="EDIT">EDIT — lecture + modification</option><option value="MANAGE">MANAGE — gestion complète</option></select></div>
            )}
            <div className="info-box">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>
              <span>Une base <b style={{ color: '#fff' }}>COMMON</b> est accessible à <b>tous les utilisateurs actifs</b> selon le niveau collectif choisi (VIEW par défaut). Aucun partage individuel n'est requis. Une base <b style={{ color: '#fff' }}>PERSONAL</b> reste privée et se partage via <b style={{ color: '#fff' }}>Gérer les accès</b>.</span>
            </div>
          </div>
          <div className="modal-footer"><button className="btn" onClick={() => setShowNewDb(false)}>Annuler</button><button className="btn btn-primary" onClick={handleCreateDb}>Créer la base</button></div>
        </div>
      </div>

      {/* Edit DB */}
      <div className={`modal-overlay ${showEditDb ? 'open' : ''}`} onClick={() => setShowEditDb(null)}>
        <div className="modal" onClick={e => e.stopPropagation()}>
          <div className="modal-head"><h3>Modifier la base</h3><button className="icon-btn" onClick={() => setShowEditDb(null)}>✕</button></div>
          <div className="modal-body">
            <div className="field-block"><label className="form-label">Nom</label><input className="form-input" value={editDbName} onChange={e => setEditDbName(e.target.value)} /></div>
            <div className="field-block"><label className="form-label">Description</label><input className="form-input" value={editDbDesc} onChange={e => setEditDbDesc(e.target.value)} /></div>
            <div className="field-block"><label className="form-label">Portée</label><select className="form-input" value={editDbScope} onChange={e => setEditDbScope(e.target.value)} disabled={!showEditDb?.access?.can_admin}><option value="PERSONAL">PERSONAL</option><option value="COMMON">COMMON</option></select></div>
            {editDbScope === 'COMMON' && (
              <div className="field-block"><label className="form-label">Niveau collectif</label><select className="form-input" value={editDbCommonPermission} onChange={e => setEditDbCommonPermission(e.target.value)} disabled={!showEditDb?.access?.can_admin}><option value="VIEW">VIEW</option><option value="EDIT">EDIT</option><option value="MANAGE">MANAGE</option></select></div>
            )}
          </div>
          <div className="modal-footer"><button className="btn" onClick={() => setShowEditDb(null)}>Annuler</button><button className="btn btn-primary" onClick={handleSaveEditDb}>Enregistrer</button></div>
        </div>
      </div>

      <div className={`modal-overlay ${showAccess ? 'open' : ''}`} onClick={() => setShowAccess(null)}>
        <div className="modal modal-wide" onClick={e => e.stopPropagation()}>
          <div className="modal-head"><h3>Accès à {showAccess?.name}</h3><button className="icon-btn" onClick={() => setShowAccess(null)}>✕</button></div>
          <div className="modal-body">
            {showAccess?.scope === 'COMMON' ? (
              <div className="info-box">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>
                <span>Cette base est <b style={{ color: '#fff' }}>COMMON</b> : son accès est <b>collectif</b> (niveau {showAccess?.common_permission || 'VIEW'}). Tous les utilisateurs actifs y ont accès — aucun partage individuel n'est nécessaire ni autorisé. Modifiez le niveau via « Modifier ».</span>
              </div>
            ) : (
              <>
                <p className="desc">Partagez cette base par email. VIEW permet la lecture, EDIT ajoute écritures et structure, MANAGE ajoute l'administration des accès.</p>
                <div className="grid-2"><input className="form-input" type="email" placeholder="utilisateur@exemple.com" value={accessEmail} onChange={e => setAccessEmail(e.target.value)} /><select className="form-input" value={grantLevel} onChange={e => setGrantLevel(e.target.value)}><option>VIEW</option><option>EDIT</option><option>MANAGE</option></select></div>
                <button className="btn btn-primary" style={{ marginTop: 12 }} onClick={grantAccess} disabled={!accessEmail.trim()}>Accorder</button>
                <div style={{ marginTop: 18 }}>
                  {accessLoading ? <div className="skeleton" style={{ height: 42 }} /> : permissions.length === 0 ? <div className="empty-state" style={{ padding: 20 }}><div className="es-title">Aucun partage</div></div> : permissions.map(permission => (
                    <div className="rel-row" key={permission.id}><span className="rel-row-col">{permission.user_email || `User #${permission.user_id}`}</span><span className="badge badge-blue">{permission.can_admin ? 'MANAGE' : permission.can_write || permission.can_ddl ? 'EDIT' : 'VIEW'}</span><button className="icon-btn sm danger" style={{ marginLeft: 'auto' }} onClick={() => revokeAccess(permission)}>✕</button></div>
                  ))}
                </div>
              </>
            )}
          </div>
          <div className="modal-footer"><button className="btn" onClick={() => setShowAccess(null)}>Fermer</button></div>
        </div>
      </div>

      <div className={`modal-overlay ${showExportFull ? 'open' : ''}`} onClick={() => setShowExportFull(false)}>
        <div className="modal" onClick={event => event.stopPropagation()}>
          <div className="modal-head"><h3>Export complet XMLForge</h3><button className="icon-btn" onClick={() => setShowExportFull(false)}>✕</button></div>
          <div className="modal-body">
            <p className="desc">Génère le projet complet réellement fourni par Flask : structure XML, données, relations et métadonnées nécessaires à la reconstruction.</p>
            <div className="field-block"><label className="form-label">Base à exporter</label><select className="form-input" value={exportTarget?.id || ''} onChange={event => setExportTarget(databases.find(item => item.id === Number(event.target.value)) || null)}><option value="">Sélectionner...</option>{databases.filter(item => item.access?.can_admin).map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div>
          </div>
          <div className="modal-footer"><button className="btn" onClick={() => setShowExportFull(false)}>Annuler</button><button className="btn btn-primary" disabled={!exportTarget} onClick={() => handleExportProject(exportTarget)}>Générer l'export</button></div>
        </div>
      </div>

      <ConflictDialog open={conflict} onClose={() => setConflict(false)} onReload={async () => { setConflict(false); setShowEditDb(null); await fetchDatabases() }} />
    </div>
  )
}
