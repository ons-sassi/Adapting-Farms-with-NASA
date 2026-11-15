import { useEffect, useState } from 'react'
import { Database, RefreshCw, RotateCcw, Server } from 'lucide-react'
import { api, API_URL, DATA_MODE } from '../api/client.js'
import { Card, PageHeader } from '../components/ui.jsx'

const DEMO_SOURCES = [
  ['Catalogue des cultures (EcoCrop + FAO-56 + AquaCrop, v6)', 'Démo'],
  ['NASA POWER, SoilGrids, SMAP, GPM, MODIS', 'Mode API uniquement'],
]
const LIVE = ['nasa_power', 'soilgrids', 'earth_engine']
const SERVICE_LABELS = {
  mysql: 'Base MySQL',
  catalogue_interface: 'Catalogue des cultures (interface)',
  catalogue_indicateurs: 'Catalogue cultures MySQL (indicateurs)',
  nasa_power: 'NASA POWER (climat)',
  soilgrids: 'ISRIC SoilGrids (sol)',
  earth_engine: 'Google Earth Engine (SMAP, GPM, MODIS)',
  groq: 'Chatbot (Groq)',
  elevenlabs: 'Voix du chatbot (ElevenLabs)',
  gemini: 'Lecture des rapports PDF (Gemini)',
  jwt: 'Clé de sécurité JWT',
}

export default function Settings() {
  const [resetDone, setResetDone] = useState(false)
  const [status, setStatus] = useState(null)
  const [statusError, setStatusError] = useState(null)
  const [checking, setChecking] = useState(false)
  useEffect(() => { api.status().then(setStatus).catch((e) => setStatusError(e.message)) }, [])
  // Test en direct : le backend appelle vraiment NASA POWER, SoilGrids et Earth Engine
  const testLive = () => {
    setChecking(true)
    setStatusError(null)
    api.status(true).then(setStatus).catch((e) => setStatusError(e.message)).finally(() => setChecking(false))
  }
  return (
    <>
      <PageHeader title="Paramètres" subtitle="Configuration de l'application et état des sources de données." />
      <div className="two-cols">
        <Card>
          <h3><Server size={18} /> Connexion aux données</h3>
          <dl className="facts">
            <div><dt>Mode actuel</dt><dd><span className="badge badge-demo">{DATA_MODE === 'demo' ? 'Démonstration' : 'API'}</span></dd></div>
            <div><dt>URL de l'API</dt><dd>{API_URL}</dd></div>
          </dl>
          {DATA_MODE === 'demo' && (
            <button className="btn btn-ghost" onClick={() => { api.resetDemo(); setResetDone(true) }}>
              <RotateCcw size={16} /> {resetDone ? 'Démo réinitialisée' : 'Réinitialiser les données de démo'}
            </button>
          )}
        </Card>
        <Card>
          <div className="card-head">
            <h3><Database size={18} /> Sources de données</h3>
            {DATA_MODE === 'api' && (
              <button className="btn btn-light" onClick={testLive} disabled={checking}>
                <RefreshCw size={16} className={checking ? 'spin' : ''} /> {checking ? 'Test en cours…' : 'Tester les connexions'}
              </button>
            )}
          </div>
          {status && !status.checked_live && DATA_MODE === 'api' && (
            <p className="muted small">« Configuré » = la clé est présente dans backend/.env. Cliquez « Tester les connexions » pour vérifier que chaque service répond vraiment.</p>
          )}
          {statusError && <p className="error-text">{statusError}</p>}
          <ul className="list static">
            {DATA_MODE === 'demo'
              ? DEMO_SOURCES.map(([name, state]) => <li key={name}><span>{name}</span><span className="badge">{state}</span></li>)
              : status && Object.entries(SERVICE_LABELS).map(([key, label]) => (
                <li key={key}>
                  <span>{label}<br /><small className="muted">{status[key]?.detail}</small></span>
                  <span className={`status status-${status[key]?.ok ? 'ok' : 'warning'}`}>{status[key]?.ok ? (status.checked_live && LIVE.includes(key) ? 'Répond' : 'Configuré') : (status.checked_live && LIVE.includes(key) ? 'En panne' : 'À configurer')}</span>
                </li>
              ))}
          </ul>
          {DATA_MODE === 'api' && <p className="muted small">Les clés se règlent dans <code>backend/.env</code> (voir CONFIGURATION.md), puis redémarrer le serveur.</p>}
        </Card>
      </div>
    </>
  )
}
