import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, Check, Droplets, Leaf, Search, Timer } from 'lucide-react'
import { api } from '../api/client.js'
import { ANALYSIS_STEPS, useAnalysisDraft } from '../components/AnalysisContext.jsx'
import { Card, DemoBadge, ErrorState, Loading, PageHeader, Stepper } from '../components/ui.jsx'

export default function CropSelection() {
  const navigate = useNavigate()
  const { draft, update } = useAnalysisDraft()
  const [parcels, setParcels] = useState(null)
  const [crops, setCrops] = useState(null)
  const [query, setQuery] = useState('')
  const [type, setType] = useState('Tous')
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([api.listParcels(), api.listCrops()])
      .then(([p, c]) => {
        setParcels(p)
        setCrops(c)
        if (!draft.parcelId && p[0]) update({ parcelId: p[0].id })
      })
      .catch((e) => setError(e.message))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const types = useMemo(() => ['Tous', ...new Set((crops || []).map((c) => c.type))], [crops])
  const visible = (crops || []).filter((c) =>
    (type === 'Tous' || c.type === type) && c.name.toLowerCase().includes(query.toLowerCase()))

  const toggle = (id) => update({ crops: draft.crops.includes(id) ? draft.crops.filter((c) => c !== id) : [...draft.crops, id] })

  if (error) return <ErrorState message={error} />
  if (!crops) return <Loading />

  return (
    <>
      <PageHeader back="/terrains" title="Choix des cultures" subtitle="Sélectionnez les cultures que vous souhaitez ou pouvez cultiver." />
      <Stepper steps={ANALYSIS_STEPS} current={1} />

      <Card className="inline-form">
        <label>Parcelle analysée
          <select value={draft.parcelId || ''} onChange={(e) => update({ parcelId: e.target.value })}>
            {parcels.map((p) => <option key={p.id} value={p.id}>{p.name} — {p.areaHa?.toFixed(1)} ha</option>)}
          </select>
        </label>
        <div className="search"><Search size={18} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Rechercher une culture" /></div>
        <div className="segmented">
          {types.map((t) => <button key={t} className={t === type ? 'active' : ''} onClick={() => setType(t)}>{t}</button>)}
        </div>
      </Card>

      <div className="section-title">
        <span>{draft.crops.length} culture(s) sélectionnée(s) — minimum 2</span>
        <DemoBadge label="Caractéristiques : démo" />
      </div>

      <div className="crop-grid">
        {visible.map((crop) => {
          const selected = draft.crops.includes(crop.id)
          return (
            <button key={crop.id} className={`crop-card ${selected ? 'selected' : ''}`} onClick={() => toggle(crop.id)}>
              <span className="crop-check">{selected && <Check size={16} />}</span>
              <span className="crop-icon"><Leaf size={22} /></span>
              <strong>{crop.name}</strong>
              <small>{crop.type} · {crop.family}</small>
              <ul>
                <li><Droplets size={14} /> Eau : {crop.water}</li>
                <li><Timer size={14} /> {crop.cycle} · {crop.season}</li>
                <li><Leaf size={14} /> Sol : {crop.soil}</li>
              </ul>
              {crop.nFixer && <span className="tag">Fixe l'azote</span>}
            </button>
          )
        })}
      </div>

      <div className="center-actions">
        <button className="btn btn-primary btn-lg" disabled={draft.crops.length < 2 || !draft.parcelId} onClick={() => navigate('/analyse/priorites')}>
          Continuer <ArrowRight size={18} />
        </button>
      </div>
    </>
  )
}
