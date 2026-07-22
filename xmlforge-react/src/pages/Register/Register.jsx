import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Input } from '../../components/Input/Input'
import { Button } from '../../components/Button/Button'
import { Icons } from '../../utils/icons'
import { AuthBackground } from '../Login/Login'
import '../Login/Login.css'
import { useToast } from '../../components/Toast/Toast'
import { useAuth } from '../../context/AuthContext'

export function Register(){
  const navigate = useNavigate()
  const { notify } = useToast()
  const { register } = useAuth()
  const [form, setForm] = useState({ name:'', email:'', pass:'', confirm:'' })
  const [loading, setLoading] = useState(false)

  const onChange = (k)=>(e)=> setForm(f=>({...f, [k]: e.target.value}))

  const onSubmit = async (e)=>{
    e.preventDefault()
    const { name, email, pass, confirm } = form
    if(!name || !email || !pass || !confirm){
      notify('error','Champs manquants','Veuillez remplir tous les champs.')
      return
    }
    if(pass !== confirm){
      notify('error','Mots de passe différents','Les mots de passe ne correspondent pas.')
      return
    }
    if(pass.length < 6){
      notify('error','Mot de passe trop court','Au moins 6 caractères.')
      return
    }
    setLoading(true)
    try{
      await register({ full_name: name, email, password: pass })
      notify('success','Inscription réussie',`Bienvenue sur XMLForge, ${name} !`)
      navigate('/login')
    }catch(err){
      notify('error','Échec inscription', err.message)
    }finally{
      setLoading(false)
    }
  }

  return (
    <div className="auth-screen">
      <AuthBackground />
      <div className="auth-card wide">
        <div className="auth-logo">{Icons.userPlus}</div>
        <h1 className="auth-title">Créer un compte</h1>
        <p className="auth-sub">Rejoignez XMLForge et commencez à gérer vos bases</p>

        <form onSubmit={onSubmit} noValidate>
          <Input label="Nom complet" id="reg-name" icon={Icons.user} placeholder="Jean Dupont" value={form.name} onChange={onChange('name')} />
          <Input label="Email" id="reg-email" icon={Icons.mail} type="email" placeholder="dev@xmlforge.io" value={form.email} onChange={onChange('email')} />
          <Input label="Mot de passe" id="reg-pass" icon={Icons.lock} type="password" placeholder="••••••••" value={form.pass} onChange={onChange('pass')} />
          <Input label="Confirmer le mot de passe" id="reg-pass-confirm" icon={Icons.lock} type="password" placeholder="••••••••" value={form.confirm} onChange={onChange('confirm')} />
          <Button type="submit" variant="primary" fullWidth className="auth-btn" leftIcon={Icons.userPlus} disabled={loading}>
            {loading ? 'Inscription...' : "S'inscrire"}
          </Button>
        </form>

        <p className="auth-footer">Déjà un compte ? <Link to="/login">Se connecter</Link></p>
      </div>

      <div className="auth-badge-row">
        <span>v2.0.0</span>
        <span>Backend Flask + JWT</span>
        <span>XML → SQL Engine</span>
      </div>
    </div>
  )
}
