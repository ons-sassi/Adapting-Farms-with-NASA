import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Award, BookmarkCheck, Download, FileDown, Printer, SlidersHorizontal, ThumbsDown, ThumbsUp, TriangleAlert } from 'lucide-react'
import { api, DATA_MODE } from '../api/client.js'
import { compositeIndices } from '../data/demo/demoData.js'
import { useCropNames } from '../components/useCropNames.js'
import { useAnalysisDraft } from '../components/AnalysisContext.jsx'
import { Card, DemoBadge, ErrorState, Loading, PageHeader, ScoreRing } from '../components/ui.jsx'

const SERIES_COLORS = ['#1f6f3a', '#7fb35a', '#c9a227']

function download(filename, content, type) {
  const url = URL.createObjectURL(new Blob([content], { type }))
  const a = Object.assign(document.createElement('a'), { href: url, download: filename })
  a.click()
  URL.revokeObjectURL(url)
}

function Timeline({ years, cropName }) {
  return (
    <ol className="timeline">
      {years.map((crop, i) => (
        <li key={i}><small>Année {i + 1}</small><strong>{cropName(crop)}</strong></li>
      ))}
    </ol>
  )
}

export default function Results() {
  const { analysisId } = useParams()
  const navigate = useNavigate()
  const { update } = useAnalysisDraft()
  const [analysis, setAnalysis] = useState(null)
  const [parcel, setParcel] = useState(null)
  const [error, setError] = useState(null)
  const [savedId, setSavedId] = useState(null)
  const cropName = useCropNames()
  const isDemo = DATA_MODE === 'demo' || analysis?.isDemoResult

  useEffect(() => {
    api.getAnalysis(analysisId)
      .then((a) => {
        setAnalysis(a)
        return api.getParcel(a.parcelId).then(setParcel).catch(() => null)
      })
      .catch((e) => setError(e.message))
  }, [analysisId])

  const recommended = useMemo(() => analysis?.rotations.find((r) => r.id === analysis.recommendedId), [analysis])
  const chartData = useMemo(() => compositeIndices.map((idx) => ({
    name: idx.short,
    ...Object.fromEntries((analysis?.rotations || []).map((r) => [r.name, r.indices[idx.id]])),
  })), [analysis])

  if (error) return <ErrorState message={error} />
  if (!analysis) return <Loading />

  const save = async (rotation) => {
    try {
      await api.saveRotation(analysis.id, rotation)
      setSavedId(rotation.id)
    } catch (e) {
      setError(e.message)
    }
  }

  const exportCsv = () => {
    const header = ['Rotation', 'Score', ...Array.from({ length: analysis.horizon }, (_, i) => `Année ${i + 1}`), ...compositeIndices.map((i) => i.label)]
    const rows = analysis.rotations.map((r) => [r.name, r.score, ...r.years.map(cropName), ...compositeIndices.map((i) => r.indices[i.id] ?? '')])
    const csv = [header, ...rows].map((row) => row.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(';')).join('\n')
    download(`agrisense-analyse-${analysis.id}.csv`, `﻿${isDemo ? '# Données de démonstration\n' : ''}${csv}`, 'text/csv;charset=utf-8')
  }

  const editPriorities = () => {
    update({ parcelId: analysis.parcelId, crops: analysis.crops, priorities: analysis.priorities })
    navigate('/analyse/priorites')
  }

  return (
    <div className="results">
      <PageHeader back="/analyses" title="Résultats de l'analyse"
        subtitle={`${parcel?.name || 'Parcelle'} · horizon ${analysis.horizon} ans · ${analysis.createdAt}`}
        actions={<>
          <button className="btn btn-ghost" onClick={editPriorities}><SlidersHorizontal size={16} /> Modifier les priorités</button>
          <button className="btn btn-ghost" onClick={exportCsv}><Download size={16} /> CSV</button>
          <button className="btn btn-ghost" onClick={() => download(`agrisense-analyse-${analysis.id}.json`, JSON.stringify({ demo: isDemo, ...analysis }, null, 2), 'application/json')}><FileDown size={16} /> JSON</button>
          <button className="btn btn-ghost" onClick={() => window.print()}><Printer size={16} /> Rapport</button>
        </>} />

      {isDemo ? (
        <div className="notice">Résultats de démonstration : les rotations, scores et indices ci-dessous sont fictifs.</div>
      ) : (
        <div className="notice">
          Rotations générées par le moteur du backend (règles d'exclusion, calendrier FAO, successions).
          {' '}Données utilisées : {(analysis.dataSources || ['Catalogue des cultures']).join(' · ')}.
          {analysis.dataQuality !== 'mesures' && ' Sans climat NASA POWER (pas d\'accès Internet côté serveur ?), les scores eau et climat sont estimés à partir du catalogue.'}
          {analysis.startDate && <> Campagne de départ : {analysis.startDate.slice(0, 4)}–{Number(analysis.startDate.slice(0, 4)) + 1}.</>}
          {analysis.excludedCrops?.length > 0 && <> Cultures écartées : {analysis.excludedCrops.map((c) => `${c.name} (${c.reason})`).join(' ; ')}.</>}
        </div>
      )}

      {recommended && (
        <Card className="recommended">
          <div className="rec-head">
            <span className="rec-badge"><Award size={18} /> Rotation recommandée</span>
            <DemoBadge />
          </div>
          <div className="rec-body">
            <ScoreRing value={recommended.score} size={110} />
            <div>
              <h2>{recommended.name}</h2>
              <p>{recommended.explanation}</p>
              <Timeline years={recommended.years} cropName={cropName} />
            </div>
            <div className="rec-actions">
              <button className="btn btn-primary" onClick={() => save(recommended)} disabled={savedId === recommended.id}>
                <BookmarkCheck size={18} /> {savedId === recommended.id ? 'Enregistrée' : 'Enregistrer'}
              </button>
            </div>
          </div>
        </Card>
      )}

      <div className="two-cols">
        <Card>
          <div className="card-head"><h3>Sous-scores (sur 100)</h3><DemoBadge /></div>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="name" />
              <YAxis domain={[0, 100]} />
              <Tooltip />
              <Legend />
              {analysis.rotations.map((r, i) => <Bar key={r.id} dataKey={r.name} fill={SERIES_COLORS[i % 3]} radius={[6, 6, 0, 0]} />)}
            </BarChart>
          </ResponsiveContainer>
          <ul className="index-legend">
            {compositeIndices.map((i) => <li key={i.id}><strong>{i.short}</strong> {i.label}</li>)}
          </ul>
        </Card>
        <Card>
          <div className="card-head"><h3>Scores globaux</h3><DemoBadge /></div>
          <div className="score-row">
            {analysis.rotations.map((r) => (
              <div key={r.id} className={r.id === analysis.recommendedId ? 'best' : ''}>
                <ScoreRing value={r.score} />
                <strong>{r.name}</strong>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <h2 className="section-h">Comparaison des rotations</h2>
      <div className="rotation-grid">
        {analysis.rotations.map((r) => (
          <Card key={r.id} className={`rotation ${r.id === analysis.recommendedId ? 'is-best' : ''}`}>
            <div className="card-head">
              <h3>{r.name}</h3>
              <span className="score-pill">{r.score}/100</span>
            </div>
            <Timeline years={r.years} cropName={cropName} />
            {r.calendar && (
              <ul className="calendar-list">
                {r.calendar.map((c, k) => <li key={k}><span>{cropName(c.crop)}</span><small>semis {c.sowing} · récolte {c.harvest}</small></li>)}
              </ul>
            )}
            <div className="index-bars">
              {compositeIndices.map((i) => (
                <div key={i.id}><span>{i.short}</span><i><b style={{ width: `${r.indices[i.id] ?? 0}%` }} /></i><em>{r.indices[i.id] ?? 'n.d.'}</em></div>
              ))}
            </div>
            <ul className="pros">{r.pros.map((p) => <li key={p}><ThumbsUp size={14} /> {p}</li>)}</ul>
            <ul className="cons">{r.cons.map((p) => <li key={p}><ThumbsDown size={14} /> {p}</li>)}</ul>
            <ul className="risks">{r.risks.map((p) => <li key={p}><TriangleAlert size={14} /> {p}</li>)}</ul>
            <p className="muted small">{r.explanation}</p>
            <button className="btn btn-light" onClick={() => save(r)} disabled={savedId === r.id}>
              <BookmarkCheck size={16} /> {savedId === r.id ? 'Enregistrée' : 'Enregistrer cette rotation'}
            </button>
          </Card>
        ))}
      </div>
    </div>
  )
}
