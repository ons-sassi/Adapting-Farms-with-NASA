import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronDown, ChevronRight, Droplets, FlaskConical, MapPin, Pencil, Plus, Sprout, Trash2 } from 'lucide-react'
import { api } from '../api/client.js'
import { Card, DemoBadge, Empty, ErrorState, Loading, PageHeader } from '../components/ui.jsx'
import { ParcelsOverviewMap } from '../components/ParcelMap.jsx'
import { useAnalysisDraft } from '../components/AnalysisContext.jsx'

const STATUS_LABEL = { ok: 'Bon état', warning: 'À surveiller', alert: 'Alerte' }

function PhGauge({ value }) {
  const pct = Math.min(100, Math.max(0, ((value - 5) / 4) * 100))
  return (
    <div className="ph-gauge">
      <div className="ph-bar"><span style={{ left: `${pct}%` }} /></div>
      <div className="ph-scale"><small>&lt;5,5</small><strong>{value?.toFixed(1)}</strong><small>&gt;7,5</small></div>
    </div>
  )
}

export default function Parcels() {
  const navigate = useNavigate()
  const { update } = useAnalysisDraft()
  const [farms, setFarms] = useState([])
  const [parcels, setParcels] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [openFarms, setOpenFarms] = useState({})
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([api.listFarms(), api.listParcels()])
      .then(([f, p]) => {
        setFarms(f)
        setParcels(p)
        setSelectedId(p[0]?.id ?? null)
        setOpenFarms(Object.fromEntries(f.map((x) => [x.id, true])))
      })
      .catch((e) => setError(e.message))
  }, [])

  const selected = useMemo(() => parcels?.find((p) => p.id === selectedId), [parcels, selectedId])

  const remove = async (id) => {
    if (!window.confirm('Supprimer cette parcelle ?')) return
    await api.deleteParcel(id)
    setParcels((list) => list.filter((p) => p.id !== id))
    setSelectedId(null)
  }

  const analyse = () => {
    update({ parcelId: selected.id })
    navigate('/analyse/cultures')
  }

  if (error) return <ErrorState message={error} />
  if (!parcels) return <Loading />

  return (
    <>
      <PageHeader title="Mes terrains" subtitle="Visualisez et gérez vos parcelles."
        actions={<button className="btn btn-primary" onClick={() => navigate('/terrains/nouveau')}><Plus size={18} /> Nouvelle parcelle</button>} />

      {parcels.length === 0 ? (
        <Card><Empty icon={MapPin} title="Aucune parcelle">
          <button className="btn btn-primary" onClick={() => navigate('/terrains/nouveau')}>Délimiter ma première parcelle</button>
        </Empty></Card>
      ) : (
        <div className="dashboard">
          <Card className="tree">
            <div className="tree-title">Toutes les exploitations</div>
            {farms.map((farm) => {
              const items = parcels.filter((p) => p.farmId === farm.id)
              const open = openFarms[farm.id]
              return (
                <div key={farm.id}>
                  <button className="tree-farm" onClick={() => setOpenFarms((o) => ({ ...o, [farm.id]: !open }))}>
                    {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />} {farm.name}
                  </button>
                  {open && items.map((p) => (
                    <button key={p.id} className={`tree-item ${p.id === selectedId ? 'active' : ''}`} onClick={() => setSelectedId(p.id)}>
                      <span className={`dot dot-${p.status}`} /> {p.name} <small>{p.updatedAt}</small>
                    </button>
                  ))}
                </div>
              )
            })}
            {parcels.some((p) => !farms.find((f) => f.id === p.farmId)) && (
              <div>
                <div className="tree-farm static">Autres parcelles</div>
                {parcels.filter((p) => !farms.find((f) => f.id === p.farmId)).map((p) => (
                  <button key={p.id} className={`tree-item ${p.id === selectedId ? 'active' : ''}`} onClick={() => setSelectedId(p.id)}>
                    <span className={`dot dot-${p.status || 'ok'}`} /> {p.name}
                  </button>
                ))}
              </div>
            )}
          </Card>

          <div className="dash-center">
            {selected ? (
              <>
                <Card>
                  <div className="card-head">
                    <h2><Sprout size={20} /> {selected.name}</h2>
                    <DemoBadge />
                  </div>
                  <dl className="facts">
                    <div><dt>Culture actuelle</dt><dd>{selected.crop || '—'}</dd></div>
                    <div><dt>Surface</dt><dd>{selected.areaHa?.toFixed(2)} ha</dd></div>
                    <div><dt>Irrigation</dt><dd>{selected.irrigation || '—'}</dd></div>
                    <div><dt>Zone</dt><dd>{selected.zone || '—'}</dd></div>
                    <div><dt>État</dt><dd><span className={`status status-${selected.status || 'ok'}`}>{STATUS_LABEL[selected.status] || 'Bon état'}</span></dd></div>
                  </dl>
                </Card>
                <Card>
                  <div className="card-head"><h3><FlaskConical size={18} /> pH du sol</h3><DemoBadge /></div>
                  {selected.ph ? <PhGauge value={selected.ph} /> : <p className="muted">Aucune analyse de sol.</p>}
                </Card>
                <Card>
                  <div className="card-head"><h3><Droplets size={18} /> Humidité du sol</h3><span className="badge">Bientôt</span></div>
                  <p className="muted">Disponible après l'intégration des données SMAP.</p>
                </Card>
                <div className="row-actions">
                  <button className="btn btn-primary" onClick={analyse}>Analyser cette parcelle</button>
                  <button className="btn btn-ghost" onClick={() => navigate(`/terrains/${selected.id}`)}><Pencil size={16} /> Modifier</button>
                  <button className="btn btn-ghost danger" onClick={() => remove(selected.id)}><Trash2 size={16} /> Supprimer</button>
                </div>
              </>
            ) : (
              <Card><Empty icon={MapPin} title="Sélectionnez une parcelle" /></Card>
            )}
          </div>

          <Card className="dash-map">
            <ParcelsOverviewMap parcels={parcels.filter((p) => p.geometry?.length)} selectedId={selectedId} onSelect={setSelectedId} />
            <div className="legend">
              <strong>État</strong>
              {Object.entries(STATUS_LABEL).map(([k, v]) => <span key={k}><i className={`dot dot-${k}`} /> {v}</span>)}
            </div>
          </Card>
        </div>
      )}
    </>
  )
}
