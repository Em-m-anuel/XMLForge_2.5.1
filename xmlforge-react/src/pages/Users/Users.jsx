import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sidebar } from '../../components/Sidebar/Sidebar'
import { useToast } from '../../components/Toast/Toast'
import apiClient from '../../services/api'

export function UsersPage() {
  const navigate = useNavigate()
  const { notify } = useToast()
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [showEdit, setShowEdit] = useState(null)
  const [showReset, setShowReset] = useState(null)
  const [form, setForm] = useState({ full_name: '', email: '', password: '', is_active: true })
  const [resetPwd, setResetPwd] = useState('')

  const fetchUsers = useCallback(async () => {
    setLoading(true)
    try {
      const res = await apiClient.get(`/users?search=${encodeURIComponent(search)}&include_inactive=true`)
      setUsers(res.data || [])
    } catch (err) {
      notify('error', 'Erreur', err.message)
    } finally {
      setLoading(false)
    }
  }, [search, notify])

  useEffect(() => { fetchUsers() }, [fetchUsers])

  const handleCreate = async () => {
    if (!form.full_name.trim() || !form.email.trim() || !form.password) {
      notify('error', 'Champs requis', 'Nom, email et mot de passe obligatoires')
      return
    }
    try {
      const res = await apiClient.post('/users', form)
      setUsers(prev => [res.data, ...prev])
      setShowCreate(false)
      setForm({ full_name: '', email: '', password: '', is_active: true })
      notify('success', 'Utilisateur créé', `${res.data.email} créé`)
    } catch (err) {
      notify('error', 'Erreur création', err.message)
    }
  }

  const handleEdit = async () => {
    if (!showEdit) return
    try {
      const res = await apiClient.put(`/users/${showEdit.id}`, {
        full_name: form.full_name,
        email: form.email,
        is_active: form.is_active
      })
      setUsers(prev => prev.map(u => u.id === res.data.id ? res.data : u))
      setShowEdit(null)
      notify('success', 'Modifié', `${res.data.email} mis à jour`)
    } catch (err) {
      notify('error', 'Erreur', err.message)
    }
  }

  const handleDelete = async (user) => {
    if (!window.confirm(`Supprimer définitivement ${user.email} ?`)) return
    try {
      await apiClient.delete(`/users/${user.id}`)
      setUsers(prev => prev.filter(u => u.id !== user.id))
      notify('error', 'Supprimé', `${user.email} supprimé`)
    } catch (err) {
      notify('error', 'Erreur', err.message)
    }
  }

  const handleReset = async () => {
    if (!showReset) return
    if (!resetPwd || resetPwd.length < 6) {
      notify('error', 'Mot de passe faible', '6 caractères minimum')
      return
    }
    try {
      await apiClient.post(`/users/${showReset.id}/reset-password`, { new_password: resetPwd })
      setShowReset(null)
      setResetPwd('')
      notify('success', 'Mot de passe réinitialisé', `Pour ${showReset.email}`)
    } catch (err) {
      notify('error', 'Erreur', err.message)
    }
  }

  const handleToggleActive = async (user) => {
    try {
      const res = await apiClient.post(`/users/${user.id}/toggle-active`)
      setUsers(prev => prev.map(u => u.id === res.data.id ? res.data : u))
      notify('success', user.is_active ? 'Désactivé' : 'Activé', `${user.email} ${res.data.is_active ? 'activé' : 'désactivé'}`)
    } catch (err) {
      notify('error', 'Erreur', err.message)
    }
  }

  const openEdit = (user) => {
    setForm({ full_name: user.full_name, email: user.email, password: '', is_active: user.is_active })
    setShowEdit(user)
  }

  return (
    <div className="screen active" id="screen-users">
      <aside className="sidebar">
        <Sidebar active="users" />
      </aside>
      <div className="dash-main">
        <div className="page-header">
          <a className="back-link" href="#" onClick={(e) => { e.preventDefault(); navigate('/dashboard') }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M19 12H5"/><path d="M12 19l-7-7 7-7"/></svg>
            Bases de données
          </a>
        </div>
        <div className="dash-content">
          <div className="dash-head">
            <div>
              <h1>Gestion des utilisateurs</h1>
              <p>{users.length} utilisateurs · réservé à nyx@xmlforge.io</p>
            </div>
            <div className="dash-actions">
              <div className="topbar-search" style={{ width: '260px' }}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
                <input type="text" placeholder="Rechercher email ou nom..." value={search} onChange={e => setSearch(e.target.value)} />
              </div>
              <button className="btn btn-primary" onClick={() => { setForm({ full_name: '', email: '', password: '', is_active: true }); setShowCreate(true) }}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 11h-6M16 5h6M19 2v6"/></svg>
                Nouvel utilisateur
              </button>
            </div>
          </div>

          <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', overflow: 'auto', background: 'var(--card)' }}>
            <table className="audit-table">
              <thead>
                <tr>
                  <th>Utilisateur</th>
                  <th>Email</th>
                  <th>Statut</th>
                  <th>Créé le</th>
                  <th>Dernière connexion</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  [...Array(5)].map((_, i) => (
                    <tr key={i}><td colSpan={6}><div className="skeleton" style={{ height: '20px' }}></div></td></tr>
                  ))
                ) : users.length === 0 ? (
                  <tr><td colSpan={6}><div className="empty-state"><div className="es-title">Aucun utilisateur</div><div className="es-desc">Aucun utilisateur ne correspond à la recherche.</div></div></td></tr>
                ) : (
                  users.map(u => (
                    <tr key={u.id}>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <div className="avatar" style={{ width: '28px', height: '28px', fontSize: '11px' }}>{u.full_name?.slice(0,2).toUpperCase() || 'U'}</div>
                          <span style={{ fontWeight: 600 }}>{u.full_name}</span>
                          {u.is_admin && <span className="badge badge-blue">ADMIN</span>}
                        </div>
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '12px' }}>{u.email}</td>
                      <td><span className={`badge ${u.is_active ? 'badge-green' : 'badge-red'}`}><span className="badge-dot" style={{ background: u.is_active ? '#22C55E' : '#EF4444' }}></span>{u.is_active ? 'ACTIF' : 'DÉSACTIVÉ'}</span></td>
                      <td className="date-cell">{u.created_at ? new Date(u.created_at).toLocaleString('fr-FR') : '—'}</td>
                      <td className="date-cell">{u.last_login ? new Date(u.last_login).toLocaleString('fr-FR') : 'Jamais'}</td>
                      <td>
                        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                          <button className="icon-btn sm" title="Modifier" onClick={() => openEdit(u)}>
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg>
                          </button>
                          <button className="icon-btn sm" title="Reset password" onClick={() => setShowReset(u)}>
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                          </button>
                          <button className="icon-btn sm" title={u.is_active ? 'Désactiver' : 'Activer'} onClick={() => handleToggleActive(u)}>
                            {u.is_active ? (
                              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M4.93 4.93l14.14 14.14"/></svg>
                            ) : (
                              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
                            )}
                          </button>
                          <button className="icon-btn sm danger" title="Supprimer" disabled={u.email?.toLowerCase() === 'nyx@xmlforge.io'} onClick={() => handleDelete(u)}>
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0-1 14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2L4 6"/></svg>
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Create Modal */}
      <div className={`modal-overlay ${showCreate ? 'open' : ''}`} onClick={() => setShowCreate(false)}>
        <div className="modal" onClick={e => e.stopPropagation()}>
          <div className="modal-head">
            <h3><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 11h-6M16 5h6M19 2v6"/></svg>Nouvel utilisateur</h3>
            <button className="icon-btn" onClick={() => setShowCreate(false)}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg></button>
          </div>
          <div className="modal-body">
            <div className="field-block"><label className="form-label">Nom complet</label><input className="form-input" value={form.full_name} onChange={e => setForm(f => ({ ...f, full_name: e.target.value }))} placeholder="ex. Jean Dupont" /></div>
            <div className="field-block"><label className="form-label">Email</label><input className="form-input" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} placeholder="jean@xmlforge.io" /></div>
            <div className="field-block"><label className="form-label">Mot de passe</label><input className="form-input" type="password" value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))} placeholder="••••••••" /></div>
            <div className="check-row"><label className="switch"><input type="checkbox" checked={form.is_active} onChange={e => setForm(f => ({ ...f, is_active: e.target.checked }))} /><span className="track"></span></label><label>Compte actif</label></div>
          </div>
          <div className="modal-footer">
            <button className="btn" onClick={() => setShowCreate(false)}>Annuler</button>
            <button className="btn btn-primary" onClick={handleCreate}>Créer</button>
          </div>
        </div>
      </div>

      {/* Edit Modal */}
      <div className={`modal-overlay ${showEdit ? 'open' : ''}`} onClick={() => setShowEdit(null)}>
        <div className="modal" onClick={e => e.stopPropagation()}>
          <div className="modal-head">
            <h3><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg>Modifier utilisateur</h3>
            <button className="icon-btn" onClick={() => setShowEdit(null)}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg></button>
          </div>
          <div className="modal-body">
            <div className="field-block"><label className="form-label">Nom complet</label><input className="form-input" value={form.full_name} onChange={e => setForm(f => ({ ...f, full_name: e.target.value }))} /></div>
            <div className="field-block"><label className="form-label">Email</label><input className="form-input" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} /></div>
            <div className="check-row"><label className="switch"><input type="checkbox" checked={form.is_active} onChange={e => setForm(f => ({ ...f, is_active: e.target.checked }))} /><span className="track"></span></label><label>Compte actif</label></div>
          </div>
          <div className="modal-footer">
            <button className="btn" onClick={() => setShowEdit(null)}>Annuler</button>
            <button className="btn btn-primary" onClick={handleEdit}>Enregistrer</button>
          </div>
        </div>
      </div>

      {/* Reset Password Modal */}
      <div className={`modal-overlay ${showReset ? 'open' : ''}`} onClick={() => setShowReset(null)}>
        <div className="modal" onClick={e => e.stopPropagation()}>
          <div className="modal-head">
            <h3><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>Réinitialiser mot de passe</h3>
            <button className="icon-btn" onClick={() => setShowReset(null)}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg></button>
          </div>
          <div className="modal-body">
            <div className="info-box"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg><span>Définir un nouveau mot de passe pour <b style={{ color: '#fff' }}>{showReset?.email}</b>. L'utilisateur devra utiliser ce nouveau mot de passe à sa prochaine connexion.</span></div>
            <div className="field-block"><label className="form-label">Nouveau mot de passe</label><input className="form-input" type="password" value={resetPwd} onChange={e => setResetPwd(e.target.value)} placeholder="••••••••" /></div>
          </div>
          <div className="modal-footer">
            <button className="btn" onClick={() => setShowReset(null)}>Annuler</button>
            <button className="btn btn-primary" onClick={handleReset}>Réinitialiser</button>
          </div>
        </div>
      </div>
    </div>
  )
}
