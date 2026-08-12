import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../components/Toast/Toast'

export function Register() {
  const navigate = useNavigate()
  const { register } = useAuth()
  const { notify } = useToast()
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [password2, setPassword2] = useState('')
  const [showPwd, setShowPwd] = useState(false)
  const [showPwd2, setShowPwd2] = useState(false)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!fullName.trim() || !email.trim() || !password) {
      notify('error', 'Champs requis', 'Veuillez remplir tous les champs')
      return
    }
    if (password !== password2) {
      notify('error', 'Mots de passe différents', 'Veuillez vérifier la confirmation')
      return
    }
    setLoading(true)
    try {
      await register({ full_name: fullName.trim(), email: email.trim(), password })
      notify('success', 'Compte créé', 'Vous pouvez maintenant vous connecter')
      navigate('/login')
    } catch (err) {
      notify('error', 'Échec inscription', err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="screen active" id="screen-register">
      <svg className="login-bg-svg" viewBox="0 0 1200 800" preserveAspectRatio="xMidYMid slice">
        <g className="drift" opacity=".5">
          <text x="60" y="120" fontFamily="JetBrains Mono" fontSize="13" fill="#3B82F6">&lt;database name="library"&gt;</text>
          <text x="90" y="150" fontFamily="JetBrains Mono" fontSize="13" fill="#22C55E">&lt;table name="book"&gt;</text>
          <text x="120" y="180" fontFamily="JetBrains Mono" fontSize="13" fill="#A0AEC0">&lt;column type="varchar"/&gt;</text>
          <text x="90" y="210" fontFamily="JetBrains Mono" fontSize="13" fill="#22C55E">&lt;/table&gt;</text>
          <text x="60" y="240" fontFamily="JetBrains Mono" fontSize="13" fill="#3B82F6">&lt;/database&gt;</text>
        </g>
        <g className="drift2" opacity=".35">
          <text x="760" y="560" fontFamily="JetBrains Mono" fontSize="13" fill="#3B82F6">CREATE TABLE client (</text>
          <text x="790" y="590" fontFamily="JetBrains Mono" fontSize="13" fill="#FFB86B">id INT PRIMARY KEY,</text>
          <text x="790" y="620" fontFamily="JetBrains Mono" fontSize="13" fill="#FFB86B">nom VARCHAR(255)</text>
          <text x="760" y="650" fontFamily="JetBrains Mono" fontSize="13" fill="#3B82F6">);</text>
        </g>
        <circle cx="1050" cy="140" r="120" fill="url(#g3)" opacity=".25" className="drift" />
        <circle cx="150" cy="650" r="160" fill="url(#g4)" opacity=".18" className="drift2" />
        <defs>
          <radialGradient id="g3"><stop offset="0%" stopColor="#3B82F6" /><stop offset="100%" stopColor="transparent" /></radialGradient>
          <radialGradient id="g4"><stop offset="0%" stopColor="#22C55E" /><stop offset="100%" stopColor="transparent" /></radialGradient>
        </defs>
      </svg>

      <div className="login-card wide">
        <div className="login-logo">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M19 8v6M22 11h-6" /></svg>
        </div>
        <h1 className="login-title">Créer un compte</h1>
        <p className="login-sub">Rejoignez l'espace collaboratif XMLForge</p>

        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="reg-name">Nom complet</label>
            <div className="field-input">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" /></svg>
              <input id="reg-name" type="text" placeholder="ex. Nyx Ndong" value={fullName} onChange={e => setFullName(e.target.value)} />
            </div>
          </div>
          <div className="field">
            <label htmlFor="reg-email">Adresse e-mail</label>
            <div className="field-input">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="4" width="20" height="16" rx="2" /><path d="m22 6-10 7L2 6" /></svg>
              <input id="reg-email" type="text" placeholder="ex. nyx@xmlforge.dev" value={email} onChange={e => setEmail(e.target.value)} />
            </div>
          </div>
          <div className="grid-2">
            <div className="field">
              <label htmlFor="reg-pass">Mot de passe</label>
              <div className="field-input">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" /></svg>
                <input id="reg-pass" type={showPwd ? 'text' : 'password'} placeholder="••••••••" value={password} onChange={e => setPassword(e.target.value)} />
                <button type="button" className="toggle-pwd" onClick={() => setShowPwd(s => !s)}>
                  {showPwd ? (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" /><line x1="1" y1="1" x2="23" y2="23" /></svg>
                  ) : (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" /><circle cx="12" cy="12" r="3" /></svg>
                  )}
                </button>
              </div>
            </div>
            <div className="field">
              <label htmlFor="reg-pass2">Confirmation</label>
              <div className="field-input">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" /></svg>
                <input id="reg-pass2" type={showPwd2 ? 'text' : 'password'} placeholder="••••••••" value={password2} onChange={e => setPassword2(e.target.value)} />
                <button type="button" className="toggle-pwd" onClick={() => setShowPwd2(s => !s)}>
                  {showPwd2 ? (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" /><line x1="1" y1="1" x2="23" y2="23" /></svg>
                  ) : (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" /><circle cx="12" cy="12" r="3" /></svg>
                  )}
                </button>
              </div>
            </div>
          </div>
          <button className="btn btn-primary login-btn" type="submit" disabled={loading}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M19 8v6M22 11h-6" /></svg>
            {loading ? 'Création...' : 'Créer mon compte'}
          </button>
        </form>
        <p className="login-footer">Déjà un compte ? <Link to="/login">Se connecter</Link></p>
      </div>
    </div>
  )
}
