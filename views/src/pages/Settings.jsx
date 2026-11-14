import { useState } from 'react'
import { Database, RotateCcw, Server } from 'lucide-react'
import { api, DATA_MODE } from '../api/client.js'
import { Card, PageHeader } from '../components/ui.jsx'

const SOURCES = [
  ['Catalogue des cultures (EcoCrop + FAO-56 + AquaCrop, v6)', 'Disponible côté serveur, non connecté'],
  ['NASA POWER (climat journalier)', 'Prévu'],
  ['SoilGrids (propriétés du sol)', 'Prévu'],
  ['SMAP (humidité du sol)', 'Prévu'],
  ['GPM IMERG (précipitations)', 'Prévu'],
  ['4 indices composites', 'En attente du document de définition'],
]

export default function Settings() {
  const [resetDone, setResetDone] = useState(false)
  return (
    <>
      <PageHeader title="Paramètres" subtitle="Configuration de l'application et état des sources de données." />
      <div className="two-cols">
        <Card>
          <h3><Server size={18} /> Connexion aux données</h3>
          <dl className="facts">
            <div><dt>Mode actuel</dt><dd><span className="badge badge-demo">{DATA_MODE === 'demo' ? 'Démonstration' : 'API'}</span></dd></div>
            <div><dt>URL de l'API</dt><dd>{import.meta.env.VITE_API_URL || 'http://localhost:8000/api'}</dd></div>
          </dl>
          <p className="muted small">Pour brancher FastAPI : définir <code>VITE_DATA_MODE=api</code> et <code>VITE_API_URL</code> dans <code>views/.env</code>.</p>
          {DATA_MODE === 'demo' && (
            <button className="btn btn-ghost" onClick={() => { api.resetDemo(); setResetDone(true) }}>
              <RotateCcw size={16} /> {resetDone ? 'Démo réinitialisée' : 'Réinitialiser les données de démo'}
            </button>
          )}
        </Card>
        <Card>
          <h3><Database size={18} /> Sources de données</h3>
          <ul className="list static">
            {SOURCES.map(([name, state]) => <li key={name}><span>{name}</span><span className="badge">{state}</span></li>)}
          </ul>
        </Card>
      </div>
    </>
  )
}
