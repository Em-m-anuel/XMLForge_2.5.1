import { useCallback, useEffect, useState } from 'react'
import { tcpService } from '../../services/tcpService'
import './TCPCredentials.css'

export const TCPCredentials = () => {
  const [credentials, setCredentials] = useState(null)
  const [fullCredentials, setFullCredentials] = useState(null)
  const [sessions, setSessions] = useState([])
  const [serverStatus, setServerStatus] = useState(null)
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [credentialResult, sessionResult, statusResult] = await Promise.all([
        tcpService.credentials(), tcpService.sessions(), tcpService.status(),
      ])
      if (credentialResult?.credential) {
        setCredentials(credentialResult.credential)
        setFullCredentials({
          username: credentialResult.credential.tcp_username,
          password: credentialResult.plain_password,
          tcp_host: credentialResult.credential.tcp_host,
          tcp_port: credentialResult.credential.tcp_port,
          connection_string: `xmlforge://${credentialResult.credential.tcp_username}:${credentialResult.plain_password}@${credentialResult.credential.tcp_host}:${credentialResult.credential.tcp_port}`,
        })
        setSuccess('Credentials TCP créés. Conservez ce mot de passe affiché une seule fois.')
      } else {
        setCredentials(credentialResult)
      }
      setSessions(sessionResult?.sessions || [])
      setServerStatus(statusResult)
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const reveal = async () => {
    if (!password) return
    setLoading(true)
    try {
      const result = await tcpService.reveal(password)
      setFullCredentials(result)
      setPassword('')
      setSuccess('Un nouveau mot de passe TCP a été généré et affiché une seule fois.')
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const regenerate = async () => {
    if (!window.confirm('Régénérer le mot de passe TCP ? Les anciennes connexions ne pourront plus se réauthentifier.')) return
    setLoading(true)
    try {
      const result = await tcpService.regenerate()
      setCredentials(result.credential)
      setFullCredentials({
        ...result.credential,
        username: result.credential.tcp_username,
        password: result.plain_password,
        connection_string: `xmlforge://${result.credential.tcp_username}:${result.plain_password}@${result.credential.tcp_host}:${result.credential.tcp_port}`,
      })
      setSuccess('Mot de passe TCP régénéré. Copiez-le maintenant.')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const copy = async (value, label) => {
    try {
      await navigator.clipboard.writeText(String(value))
      setSuccess(`${label} copié`)
    } catch {
      setError('Copie impossible dans ce navigateur.')
    }
  }

  return (
    <div className="tcp-credentials-container">
      {error && <div className="tcp-alert alert-error"><span>{error}</span><button onClick={() => setError(null)}>✕</button></div>}
      {success && <div className="tcp-alert alert-success"><span>{success}</span><button onClick={() => setSuccess(null)}>✕</button></div>}
      {loading && <div className="tcp-loading">Chargement...</div>}

      {serverStatus && (
        <div className={`tcp-alert ${serverStatus.running ? 'alert-success' : 'alert-error'}`}>
          <span>Serveur TCP {serverStatus.running ? 'actif' : 'indisponible'} · {serverStatus.host}:{serverStatus.port} · {serverStatus.active_sessions || 0} session(s)</span>
        </div>
      )}

      {credentials && (
        <div className="tcp-credentials-box">
          <div className="api-card-top" style={{ marginBottom: 4 }}>
            <div className="api-card-top-left">
              <div className="api-card-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22v-5"/><path d="M9 8V2"/><path d="M15 8V2"/><path d="M18 8v5a6 6 0 0 1-12 0V8Z"/></svg>
              </div>
              <div>
                <div style={{ fontWeight: 700, fontSize: '14.5px' }}>Connexion TCP/IP</div>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Credentials destinés aux applications externes. Le navigateur continue d'utiliser REST.</div>
              </div>
            </div>
            <span className={`badge ${credentials.is_active ? 'badge-green' : 'badge-gray'}`}><span className="badge-dot" style={{ background: credentials.is_active ? '#22C55E' : '#A0AEC0' }}></span>{credentials.is_active ? 'ACTIF' : 'INACTIF'}</span>
          </div>

          <div className="api-grid">
            {[
              ['Hôte', credentials.tcp_host],
              ['Port', credentials.tcp_port],
              ['Utilisateur TCP', credentials.tcp_username],
            ].map(([label, value]) => (
              <div key={label}>
                <div className="api-field-label">{label}</div>
                <div className="api-field-value">
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{value ?? '—'}</span>
                  <button className="tcp-copy-btn" onClick={() => copy(value, label)} title="Copier">📋</button>
                </div>
              </div>
            ))}
          </div>

          {!fullCredentials ? (
            <div className="tcp-password-section">
              <h3>Générer un mot de passe affichable</h3>
              <p>Le backend ne peut pas relire le hash existant. Après confirmation de votre mot de passe XMLForge, un nouveau secret TCP est généré.</p>
              <div className="tcp-password-input-group">
                <input type="password" placeholder="Mot de passe XMLForge actuel" value={password} onChange={event => setPassword(event.target.value)} onKeyDown={event => event.key === 'Enter' && reveal()} />
                <button className="tcp-action-btn tcp-primary" disabled={!password || loading} onClick={reveal}>Générer</button>
              </div>
              <button className="tcp-action-btn tcp-secondary" onClick={regenerate} disabled={loading}>Régénérer sans confirmation</button>
            </div>
          ) : (
            <div className="tcp-full-credentials">
              <h3>Credentials à copier maintenant</h3>
              <div className="tcp-info-grid">
                <div className="tcp-info-item tcp-highlight">
                  <label>Mot de passe</label>
                  <div className="tcp-value"><input readOnly value={fullCredentials.password || ''} /><button className="tcp-copy-btn" onClick={() => copy(fullCredentials.password, 'Mot de passe')}>📋</button></div>
                </div>
                <div className="tcp-info-item tcp-highlight">
                  <label>Connection String</label>
                  <div className="tcp-value"><input readOnly value={fullCredentials.connection_string || ''} /><button className="tcp-copy-btn" onClick={() => copy(fullCredentials.connection_string, 'Connection string')}>📋</button></div>
                </div>
              </div>
              <button className="tcp-action-btn tcp-secondary" onClick={() => setFullCredentials(null)}>Masquer</button>
            </div>
          )}

          <div className="tcp-examples">
            <h3>Client Python fourni par XMLForge</h3>
            <div className="tcp-example-item">
              <pre>{`from app.tcp import XMLForgeClient

client = XMLForgeClient('${credentials.tcp_host}', ${credentials.tcp_port})
client.connect('${credentials.tcp_username}', 'YOUR_TCP_PASSWORD', database='DATABASE_ID')
rows = client.select('your_table')
client.disconnect()`}</pre>
            </div>
            <p>L'identifiant de base à sélectionner est l'ID affiché dans l'URL de l'espace de travail (<code>/database/&lt;id&gt;</code>). Le mot de passe TCP est distinct du mot de passe web.</p>
            <p>Node.js et HTTP/cURL sur le port TCP ne sont pas annoncés : aucun client Node officiel ni API HTTP n'existe sur ce port.</p>
          </div>

          <div className="tcp-examples">
            <h3>Sessions TCP actives</h3>
            {sessions.length === 0 ? <p>Aucune session active.</p> : sessions.map(session => <div className="tcp-example-item" key={session.token}><code>{session.database || 'Sans base'} · {session.connected_at}</code></div>)}
          </div>
        </div>
      )}
    </div>
  )
}

export default TCPCredentials
