import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Input } from '../../components/Input/Input'
import { Button } from '../../components/Button/Button'
import { Icons } from '../../utils/icons'
import './Login.css'
import { useToast } from '../../components/Toast/Toast'
import { useAuth } from '../../context/AuthContext'

export function Login(){
  const navigate = useNavigate()
  const { notify } = useToast()
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [pass, setPass] = useState('')
  const [loading, setLoading] = useState(false)

  const onSubmit = async (e)=>{
    e.preventDefault()
    if(!email || !pass){
      notify('error','Champs manquants','Veuillez remplir tous les champs.')
      return
    }
    setLoading(true)
    try{
      await login({ email, password: pass })
      notify('success','Connexion réussie',`Bienvenue ${email}`)
      navigate('/dashboard')
    }catch(err){
      notify('error','Échec connexion', err.message)
    }finally{
      setLoading(false)
    }
  }

  return (
    <div className="auth-screen">
      <AuthBackground />
      <div className="auth-card">
        <div className="auth-logo">{Icons.logoCheck}</div>
        <h1 className="auth-title">Connexion à XMLForge</h1>
        <p className="auth-sub">Gérez vos bases de données XML et générez du SQL</p>

        <form onSubmit={onSubmit} noValidate>
          <Input
            label="Email"
            id="login-email"
            icon={Icons.mail}
            placeholder="dev@xmlforge.io"
            value={email}
            onChange={e=>setEmail(e.target.value)}
            autoComplete="email"
            type="email"
          />
          <Input
            label="Mot de passe"
            id="login-pass"
            icon={Icons.lock}
            type="password"
            placeholder="••••••••"
            value={pass}
            onChange={e=>setPass(e.target.value)}
            autoComplete="current-password"
          />
          <Button type="submit" variant="primary" fullWidth className="auth-btn" leftIcon={Icons.login} disabled={loading}>
            {loading ? 'Connexion...' : 'Connexion'}
          </Button>
        </form>

        <p className="auth-footer">Pas encore de compte ? <Link to="/register">Créer un compte</Link></p>
      </div>

      <div className="auth-badge-row">
        <span>v2.0.0</span>
        <span>XML → SQL Engine</span>
        <span>Backend Flask + JWT</span>
      </div>
    </div>
  )
}

export function AuthBackground(){
  return (
    <svg className="auth-bg-svg" viewBox="0 0 1200 800" preserveAspectRatio="xMidYMid slice" aria-hidden>
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
      <circle cx="1050" cy="140" r="120" fill="url(#g1)" opacity=".25" className="drift"/>
      <circle cx="150" cy="650" r="160" fill="url(#g2)" opacity=".18" className="drift2"/>
      <defs>
        <radialGradient id="g1"><stop offset="0%" stopColor="#3B82F6"/><stop offset="100%" stopColor="transparent"/></radialGradient>
        <radialGradient id="g2"><stop offset="0%" stopColor="#22C55E"/><stop offset="100%" stopColor="transparent"/></radialGradient>
      </defs>
    </svg>
  )
}
