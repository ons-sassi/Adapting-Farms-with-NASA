import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { BarChart3, BookmarkCheck, ChevronRight, Plus } from 'lucide-react'
import { api } from '../api/client.js'
import { demoCrops } from '../data/demo/demoData.js'
import { Card, Empty, ErrorState, Loading, PageHeader } from '../components/ui.jsx'

const cropName = (id) => demoCrops.find((c) => c.id === id)?.name || id

export default function Analyses() {
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([api.listAnalyses(), api.listSavedRotations(), api.listParcels()])
      .then(([analyses, saved, parcels]) => setData({ analyses, saved, parcels }))
      .catch((e) => setError(e.message))
  }, [])

  if (error) return <ErrorState message={error} />
  if (!data) return <Loading />
  const parcelName = (id) => data.parcels.find((p) => p.id === id)?.name || 'Parcelle supprimée'

  return (
    <>
      <PageHeader title="Analyses" subtitle="Historique de vos analyses et rotations enregistrées."
        actions={<button className="btn btn-primary" onClick={() => navigate('/analyse/cultures')}><Plus size={18} /> Nouvelle analyse</button>} />

      <div className="two-cols wide-left">
        <Card>
          <h3><BarChart3 size={18} /> Analyses</h3>
          {data.analyses.length === 0 ? <Empty title="Aucune analyse" /> : (
            <ul className="list">
              {data.analyses.map((a) => {
                const best = a.rotations.find((r) => r.id === a.recommendedId)
                return (
                  <li key={a.id}>
                    <button onClick={() => navigate(`/analyses/${a.id}`)}>
                      <span><strong>{parcelName(a.parcelId)}</strong><small>{a.createdAt} · {a.horizon} ans · {a.crops.length} cultures</small></span>
                      <span className="list-right">{best && <span className="score-pill">{best.score}/100</span>}<span className="badge badge-demo">Démo</span><ChevronRight size={18} /></span>
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </Card>
        <Card>
          <h3><BookmarkCheck size={18} /> Rotations enregistrées</h3>
          {data.saved.length === 0 ? <Empty title="Aucune rotation enregistrée"><small className="muted">Enregistrez une rotation depuis la page de résultats.</small></Empty> : (
            <ul className="list">
              {data.saved.map((r) => (
                <li key={`${r.analysisId}-${r.id}`}>
                  <button onClick={() => navigate(`/analyses/${r.analysisId}`)}>
                    <span><strong>{r.name}</strong><small>{r.years.map(cropName).join(' → ')}</small></span>
                    <span className="list-right"><span className="score-pill">{r.score}/100</span><ChevronRight size={18} /></span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </>
  )
}
