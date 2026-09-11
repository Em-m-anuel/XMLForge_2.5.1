import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sidebar } from '../../components/Sidebar/Sidebar'
import { useToast } from '../../components/Toast/Toast'
import { userService } from '../../services/userService'

export function UsersPage() {
  const navigate = useNavigate()
  const { notify } = useToast()
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [showEdit, setShowEdit] = useState(null)
  const [showResetPwd, setShowResetPwd] = useState(null)
  const [showDelete, setShowDelete] = useState(null)
  const [newPassword, setNewPassword] = useState('')
  const [form, setForm] = useState({ full_name: '', email: '', password: '', is_active: true, role: 'user' })

  const fetchUsers = useCallback(async () => {
    setLoading(true)
    try {
      setUsers(await userService.list())
    } catch (err) {
      notify('error', 'Erreur', err.message)
    } finally {
      setLoading(false)
    }
  }, [notify])

  useEffect(() => { fetchUsers() }, [fetchUsers])

  const handleCreate = async () => {
    if (!form.full_name.trim() || !form.email.trim() || !form.password) {
      notify('error', 'Champs requis', 'Nom, email et mot de passe obligatoires')
      return
    }
    try {
      const created = await userService.create(form)
      setUsers(prev => [created, ...prev])
      setShowCreate(false)
      setForm({ full_name: '', email: '', password: '', is_active: true, role: 'user' })
      notify('success', 'Utilisateur créé', `${created.email} créé`)
    } catch (err) {
      notify('error', 'Erreur création', err.message)
    }
  }

  const handleEdit = async () => {
    if (!showEdit) return
    try {
      const updated = await userService.update(showEdit.id, { role: form.role })
      setUsers(prev => prev.map(u => u.id === updated.id ? updated : u))
      setShowEdit(null)
      notify('success', 'Modifié', `${updated.email} mis à jour`)
    } catch (err) {
      notify('error', 'Erreur', err.message)
    }
  }

  const openDelete = (user) => setShowDelete(user)

  const handleDelete = async () => {
    if (!showDelete) return
    try {
      await userService.delete(showDelete.id)
      setUsers(prev => prev.filter(u => u.id !== showDelete.id))
      notify('error', 'Supprimé', `${showDelete.email} supprimé`)
      setShowDelete(null)
    } catch (err) {
      notify('error', 'Erreur', err.message)
    }
  }

  const handleToggleActive = async (user) => {
    try {
      const updated = await userService.toggleActive(user.id)
      setUsers(prev => prev.map(u => u.id === updated.id ? updated : u))
      notify('success', user.is_active ? 'Désactivé' : 'Activé', `${user.email} ${updated.is_active ? 'activé' : 'désactivé'}`)
    } catch (err) {
      notify('error', 'Erreur', err.message)
    }
  }

  const openEdit = (user) => {
    setForm({ full_name: user.full_name, email: user.email, password: '', is_active: user.is_active, role: user.role || 'user' })
    setShowEdit(user)
  }

  const openResetPwd = (user) => {
    setNewPassword('')
    setShowResetPwd(user)
  }

  const handleResetPassword = async () => {
    if (!showResetPwd) return
    if (newPassword.length < 6) {
      notify('error', 'Mot de passe trop court', 'Minimum 6 caractères requis par le backend')
      return
    }
    try {
      const updated = await userService.resetPassword(showResetPwd.id, newPassword)
      setUsers(prev => prev.map(u => u.id === updated.id ? updated : u))
      setShowResetPwd(null)
      setNewPassword('')
      notify('success', 'Mot de passe réinitialisé', `${updated.email} — les sessions existantes ont été révoquées`)
    } catch (err) {
      notify('error', 'Erreur', err.message)
    }
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
              <h1>Utilisateurs</h1>
              <p>Gestion des comptes, rôles et permissions de XMLForge</p>
            </div>
            <div className="dash-actions">
              <button className="btn btn-primary" onClick={() => { setForm({ full_name: '', email: '', password: '', is_active: true, role: 'user' }); setShowCreate(true) }}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 11h-6M16 5h6M19 2v6"/></svg>
                Nouvel utilisateur
              </button>
            </div>
          </div>

          <div className="info-box"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg><span>Les privilèges administrateur dépendent du rôle <b style={{ color: '#fff' }}>ADMIN</b> fourni par le backend. Le dernier administrateur actif est protégé côté Flask.</span></div>

          <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', overflow: 'auto', background: 'var(--card)' }}>
            <table className="audit-table">
              <thead>
                <tr>
                  <th>Utilisateur</th>
                  <th>Email</th>
                  <th>Rôle</th>
                  <th>Statut</th>
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
                        </div>
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '12px' }}>{u.email}</td>
                      <td><span className={`badge ${u.role === 'admin' ? 'badge-warn' : 'badge-blue'}`}>{String(u.role || 'user').toUpperCase()}</span></td>
                      <td><span className={`badge ${u.is_active ? 'badge-green' : 'badge-red'}`}><span className="badge-dot" style={{ background: u.is_active ? '#22C55E' : '#EF4444' }}></span>{u.is_active ? 'ACTIF' : 'DÉSACTIVÉ'}</span></td>
                      <td className="date-cell">{u.last_login ? new Date(u.last_login).toLocaleString('fr-FR') : 'Jamais'}</td>
                      <td>
                        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                          <button className="icon-btn sm" title="Modifier" onClick={() => openEdit(u)}>
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg>
                          </button>
                          <button className="icon-btn sm" title={u.is_active ? 'Désactiver' : 'Activer'} onClick={() => handleToggleActive(u)}>
                            {u.is_active ? (
                              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M4.93 4.93l14.14 14.14"/></svg>
                            ) : (
                              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
                            )}
                          </button>
                          <button className="icon-btn sm" title="Réinitialiser le mot de passe" onClick={() => openResetPwd(u)}>
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/></svg>
                          </button>
                          <button className="icon-btn sm danger" title="Supprimer" onClick={() => openDelete(u)}>
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
            <div className="field-block"><label className="form-label">Rôle</label><select className="form-input" value={form.role} onChange={e => setForm(f => ({ ...f, role: e.target.value }))}><option value="user">USER</option><option value="admin">ADMIN</option></select></div>
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
            <div className="field-block"><label className="form-label">Nom</label><div className="form-input" style={{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)' }}>{showEdit?.full_name}</div></div>
            <div className="field-block"><label className="form-label">E-mail</label><div className="form-input" style={{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)' }}>{showEdit?.email}</div></div>
            <div className="field-block"><label className="form-label">Rôle</label><select className="form-input" value={form.role} onChange={e => setForm(f => ({ ...f, role: e.target.value }))}><option value="user">USER</option><option value="admin">ADMIN</option></select></div>
          </div>
          <div className="modal-footer">
            <button className="btn" onClick={() => setShowEdit(null)}>Annuler</button>
            <button className="btn btn-primary" onClick={handleEdit}>Enregistrer</button>
          </div>
        </div>
      </div>

      {/* Delete user Modal */}
      <div className={`modal-overlay ${showDelete ? 'open' : ''}`} onClick={() => setShowDelete(null)}>
        <div className="modal" onClick={e => e.stopPropagation()}>
          <div className="modal-head">
            <h3><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0-1 14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2L4 6"/></svg>Supprimer l'utilisateur</h3>
            <button className="icon-btn" onClick={() => setShowDelete(null)}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg></button>
          </div>
          <div className="modal-body">
            <p className="desc">Voulez-vous vraiment supprimer <b style={{ color: '#fff' }}>{showDelete?.email}</b> ? Cette action est irréversible et l'utilisateur perdra immédiatement l'accès à XMLForge.</p>
          </div>
          <div className="modal-footer">
            <button className="btn" onClick={() => setShowDelete(null)}>Annuler</button>
            <button className="btn btn-danger" onClick={handleDelete}>Supprimer définitivement</button>
          </div>
        </div>
      </div>

      {/* Reset password Modal */}
      <div className={`modal-overlay ${showResetPwd ? 'open' : ''}`} onClick={() => setShowResetPwd(null)}>
        <div className="modal" onClick={e => e.stopPropagation()}>
          <div className="modal-head">
            <h3><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/></svg>Réinitialiser le mot de passe</h3>
            <button className="icon-btn" onClick={() => setShowResetPwd(null)}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg></button>
          </div>
          <div className="modal-body">
            <div className="info-box"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg><span>Le backend réinitialise le mot de passe de <b style={{ color: '#fff' }}>{showResetPwd?.email}</b>, incrémente la version de token et révoque ses sessions ainsi que ses déverrouillages de tables.</span></div>
            <div className="field-block"><label className="form-label">Nouveau mot de passe</label><input className="form-input" type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)} placeholder="Minimum 6 caractères" /></div>
          </div>
          <div className="modal-footer">
            <button className="btn" onClick={() => setShowResetPwd(null)}>Annuler</button>
            <button className="btn btn-primary" onClick={handleResetPassword}>Réinitialiser</button>
          </div>
        </div>
      </div>

    </div>
  )
}
