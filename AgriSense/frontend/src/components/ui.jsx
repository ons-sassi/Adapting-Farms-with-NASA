import { ArrowLeft, Loader2, TriangleAlert } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'
import { DATA_MODE } from '../api/client.js'

export function BackButton({ to }) {
  const navigate = useNavigate()
  return (
    <button className="back-btn" onClick={() => (to ? navigate(to) : navigate(-1))}>
      <ArrowLeft size={18} /> Retour
    </button>
  )
}

const ART = [['/terrains/', 'labour'], ['/terrains', 'oliviers'], ['/analyse/cultures', 'vert'], ['/analyse/priorites', 'ble'],
  ['/analyse/recapitulatif', 'oliviers'], ['/analyses/', 'ble'], ['/analyses', 'vert'], ['/parametres', 'labour']]
const artFor = (path) => ART.find(([p]) => path.startsWith(p))?.[1]

export function PageHeader({ title, subtitle, back, actions }) {
  const art = artFor(useLocation().pathname)
  return (
    <header className={`page-header ${art ? `has-art art-${art}` : ''}`}>
      <div>
        {back && <BackButton to={back === true ? undefined : back} />}
        <h1>{title}</h1>
        {subtitle && <p className="muted">{subtitle}</p>}
      </div>
      {actions && <div className="header-actions">{actions}</div>}
    </header>
  )
}

export function Card({ children, className = '', ...rest }) {
  return <section className={`card ${className}`} {...rest}>{children}</section>
}

export function DemoBadge({ label = 'Démo' }) {
  if (DATA_MODE === 'api') return null // données réelles : pas de badge
  return <span className="badge badge-demo" title="Donnée de démonstration, non issue d'un calcul réel">{label}</span>
}

export function Loading({ label = 'Chargement…' }) {
  return <div className="state"><Loader2 className="spin" size={22} /> {label}</div>
}

export function ErrorState({ message }) {
  return <div className="state state-error"><TriangleAlert size={20} /> {message}</div>
}

export function Empty({ icon: Icon, title, children }) {
  return (
    <div className="empty">
      {Icon && <Icon size={34} />}
      <h3>{title}</h3>
      {children}
    </div>
  )
}

export function Stepper({ steps, current }) {
  return (
    <ol className="stepper">
      {steps.map((step, i) => (
        <li key={step} className={i < current ? 'done' : i === current ? 'current' : ''}>
          <span>{i + 1}</span> {step}
        </li>
      ))}
    </ol>
  )
}

export function ScoreRing({ value, size = 84, label }) {
  const r = (size - 10) / 2
  const c = 2 * Math.PI * r
  return (
    <div className="score-ring" style={{ width: size, height: size }}>
      <svg width={size} height={size}>
        <circle cx={size / 2} cy={size / 2} r={r} className="ring-bg" />
        <circle cx={size / 2} cy={size / 2} r={r} className="ring-fg" strokeDasharray={c} strokeDashoffset={c * (1 - value / 100)} />
      </svg>
      <div><strong>{value}</strong><small>{label || '/100'}</small></div>
    </div>
  )
}
