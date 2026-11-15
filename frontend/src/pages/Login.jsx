import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { LogIn, UserPlus } from 'lucide-react'
import { api } from '../api/client.js'
import { Logo } from '../components/Layout.jsx'
import { ErrorState } from '../components/ui.jsx'

export default function Login() {
  const navigate = useNavigate()
  const location = useLocation()
  const [mode, setMode] = useState('login')
  const [form, setForm] = useState({ fullName: '', email: '', password: '' })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const set = (patch) => setForm((f) => ({ ...f, ...patch }))

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      if (mode === 'login') await api.login(form.email, form.password)
      else await api.register(form.fullName, form.email, form.password)
      navigate(location.state?.from || '/', { replace: true })
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-page">
      <form className="card auth-card" onSubmit={submit}>
        <Logo />
        <h1>{mode === 'login' ? 'Connexion' : 'Créer un compte'}</h1>
        <p className="muted">{mode === 'login' ? 'Accédez à vos parcelles et analyses.' : 'Un compte agriculteur pour enregistrer vos parcelles.'}</p>
        {mode === 'register' && (
          <label>Nom complet<input value={form.fullName} onChange={(e) => set({ fullName: e.target.value })} required minLength={2} autoComplete="name" /></label>
        )}
        <label>Email<input type="email" value={form.email} onChange={(e) => set({ email: e.target.value })} required autoComplete="email" /></label>
        <label>Mot de passe<input type="password" value={form.password} onChange={(e) => set({ password: e.target.value })} required
          minLength={mode === 'register' ? 8 : undefined} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} />
        </label>
        {mode === 'register' && <small className="muted">8 caractères minimum.</small>}
        {error && <ErrorState message={error} />}
        <button className="btn btn-primary" disabled={busy}>
          {mode === 'login' ? <><LogIn size={18} /> {busy ? 'Connexion…' : 'Se connecter'}</> : <><UserPlus size={18} /> {busy ? 'Création…' : 'Créer mon compte'}</>}
        </button>
        <button type="button" className="btn btn-quiet" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(null) }}>
          {mode === 'login' ? "Pas encore de compte ? S'inscrire" : 'Déjà inscrit ? Se connecter'}
        </button>
      </form>
    </div>
  )
}
