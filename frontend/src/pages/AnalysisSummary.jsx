import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, Play } from 'lucide-react'
import { api, DATA_MODE } from '../api/client.js'
import { priorityCriteria } from '../data/demo/demoData.js'
import { ANALYSIS_STEPS, useAnalysisDraft } from '../components/AnalysisContext.jsx'
import { Card, ErrorState, PageHeader, Stepper } from '../components/ui.jsx'

export default function AnalysisSummary() {
  const navigate = useNavigate()
  const { draft, reset } = useAnalysisDraft()
  const [parcel, setParcel] = useState(null)
  const [crops, setCrops] = useState([])
  const [running, setRunning] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (draft.parcelId) api.getParcel(draft.parcelId).then(setParcel).catch(() => setParcel(null))
    api.listCrops().then(setCrops).catch((e) => setError(e.message))
  }, [draft.parcelId])

  const selectedCrops = crops.filter((c) => draft.crops.includes(c.id))
  const ready = parcel && selectedCrops.length >= 2

  const run = async () => {
    setRunning(true)
    setError(null)
    try {
      const analysis = await api.createAnalysis({
        parcelId: draft.parcelId, crops: draft.crops, priorities: draft.priorities,
        horizon: draft.constraints.horizon, constraints: draft.constraints,
      })
      reset()
      navigate(`/analyses/${analysis.id}`)
    } catch (e) {
      setError(e.message)
      setRunning(false)
    }
  }

  return (
    <>
      <PageHeader back="/analyse/priorites" title="Récapitulatif" subtitle="Vérifiez vos choix avant de lancer l'analyse." />
      <Stepper steps={ANALYSIS_STEPS} current={3} />

      <div className="summary-grid">
        <Card>
          <h3>Parcelle</h3>
          {parcel ? <p><strong>{parcel.name}</strong><br />{parcel.areaHa?.toFixed(2)} ha · {parcel.zone || 'zone non renseignée'}<br />{parcel.irrigation}</p>
            : <p className="muted">Aucune parcelle sélectionnée.</p>}
          <button className="link" onClick={() => navigate('/analyse/cultures')}>Modifier</button>
        </Card>
        <Card>
          <h3>Cultures ({selectedCrops.length})</h3>
          <div className="chips-select static">{selectedCrops.map((c) => <span key={c.id}>{c.name}</span>)}</div>
          <button className="link" onClick={() => navigate('/analyse/cultures')}>Modifier</button>
        </Card>
        <Card>
          <h3>Priorités</h3>
          <ul className="mini-bars">
            {priorityCriteria.map((c) => (
              <li key={c.id}><span>{c.label}</span><i style={{ width: `${draft.priorities[c.id] * 20}%` }} /></li>
            ))}
          </ul>
          <button className="link" onClick={() => navigate('/analyse/priorites')}>Modifier</button>
        </Card>
        <Card>
          <h3>Contraintes</h3>
          <p>Horizon : <strong>{draft.constraints.horizon} ans</strong><br />
            Budget : {draft.constraints.budget ? `${draft.constraints.budget} DT/ha/an` : 'non renseigné'}<br />
            Cultures interdites : {draft.constraints.forbidden.length || 'aucune'}</p>
        </Card>
      </div>

      {DATA_MODE === 'demo' && (
        <div className="notice">Mode démonstration : le moteur d'analyse n'est pas encore connecté. Le résultat affiché sera un exemple fictif reprenant vos choix.</div>
      )}
      {error && <ErrorState message={error} />}
      <div className="center-actions">
        <button className="btn btn-primary btn-lg" disabled={!ready || running} onClick={run}>
          {running ? <><Loader2 className="spin" size={18} /> Analyse en cours…</> : <><Play size={18} /> Lancer l'analyse</>}
        </button>
      </div>
    </>
  )
}
