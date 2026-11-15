import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowRight, FileText, MapPin, Pencil, UploadCloud, X } from 'lucide-react'
import { api, DATA_MODE } from '../api/client.js'
import { Card, ErrorState, Loading, PageHeader } from '../components/ui.jsx'
import { ParcelDrawMap, polygonAreaHa } from '../components/ParcelMap.jsx'
import MapOverlay from '../components/MapOverlay.jsx'
import { useAnalysisDraft } from '../components/AnalysisContext.jsx'

const ZONES = ['Kroumirie - Mogods', 'Sub-humide', 'Semi-aride à hiver frais', 'Nord-Est et Cap Bon', 'Dorsale et Tell (Kairouan)', 'Basse steppe', 'Sidi Bouzid']
const EMPTY = { name: '', farmId: DATA_MODE === 'api' ? 'main' : 'farm-kairouan', crop: '', irrigation: 'Pluviale', zone: '', ph: null, geometry: [], status: 'ok', documents: [] }

function shapePoints(geo) {
  const lats = geo.map((p) => p[0]), lons = geo.map((p) => p[1])
  const minLat = Math.min(...lats), maxLat = Math.max(...lats), minLon = Math.min(...lons), maxLon = Math.max(...lons)
  const k = Math.min(90 / ((maxLon - minLon) || 1), 50 / ((maxLat - minLat) || 1))
  const ox = (100 - (maxLon - minLon) * k) / 2, oy = (60 - (maxLat - minLat) * k) / 2
  return geo.map(([la, lo]) => `${(ox + (lo - minLon) * k).toFixed(1)},${(oy + (maxLat - la) * k).toFixed(1)}`).join(' ')
}

function parseGeoJson(text) {
  const data = JSON.parse(text)
  const feature = data.type === 'FeatureCollection' ? data.features?.[0] : data
  const geom = feature?.geometry || feature
  if (geom?.type !== 'Polygon') throw new Error('Le fichier doit contenir un polygone (GeoJSON).')
  return geom.coordinates[0].slice(0, -1).map(([lon, lat]) => [lat, lon])
}

export default function ParcelEditor() {
  const { parcelId } = useParams()
  const navigate = useNavigate()
  const { update } = useAnalysisDraft()
  const fileInput = useRef(null)
  const [parcel, setParcel] = useState(parcelId ? null : EMPTY)
  const [mapOpen, setMapOpen] = useState(false)
  const [originRect, setOriginRect] = useState(null)
  const teaserRef = useRef(null)
  const openMap = () => { setOriginRect(teaserRef.current?.getBoundingClientRect() || null); setMapOpen(true) }
  const [error, setError] = useState(null)
  const [fileError, setFileError] = useState(null)
  const [saving, setSaving] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [reading, setReading] = useState(false)

  useEffect(() => {
    if (parcelId) api.getParcel(parcelId).then((p) => setParcel({ documents: [], ...p })).catch((e) => setError(e.message))
  }, [parcelId])

  const set = (patch) => setParcel((p) => ({ ...p, ...patch }))

  const handleFiles = async (files) => {
    setFileError(null)
    const file = files?.[0]
    if (!file) return
    const name = file.name.toLowerCase()
    try {
      if (name.endsWith('.geojson') || name.endsWith('.json')) {
        const geometry = parseGeoJson(await file.text())
        set({ geometry, areaHa: polygonAreaHa(geometry) })
      } else if (/\.(pdf|png|jpe?g|webp)$/.test(name)) {
        const doc = { name: file.name, size: file.size }
        set({ documents: [...(parcel.documents || []), doc] })
        if (DATA_MODE === 'api') {
          // Lecture automatique du rapport de sol (Gemini côté backend) : on récupère le pH s'il est trouvé.
          setReading(true)
          try {
            const { ph } = await api.extractDocument(file)
            if (ph != null) set({ ph })
            else setFileError("Document lu, mais aucun pH n'a été trouvé : saisissez-le à la main.")
          } finally {
            setReading(false)
          }
        }
      } else {
        setFileError('Formats acceptés : PDF ou image (rapport de sol), GeoJSON (limites de parcelle).')
      }
    } catch (e) {
      setFileError(e.message)
    }
  }

  const submit = async (event) => {
    event.preventDefault()
    if (!parcel.name.trim()) return setError('Donnez un nom à la parcelle.')
    if ((parcel.geometry || []).length < 3) return setError('Délimitez la parcelle sur la carte ou importez un fichier GeoJSON.')
    setSaving(true)
    setError(null)
    try {
      const saved = await api.saveParcel({ ...parcel, areaHa: polygonAreaHa(parcel.geometry) })
      update({ parcelId: saved.id })
      navigate(parcelId ? '/terrains' : '/analyse/cultures')
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const hasShape = (parcel?.geometry || []).length >= 3

  if (!parcel) return error ? <ErrorState message={error} /> : <Loading />

  return (
    <form onSubmit={submit} className="editor">
      {mapOpen && <MapOverlay originRect={originRect} geometry={parcel.geometry} onChange={(geometry) => set({ geometry })} onClose={() => setMapOpen(false)} />}
      <PageHeader back="/terrains" title={parcelId ? 'Modifier le terrain' : 'Mon terrain'} subtitle="Importez les informations de votre parcelle" />

      <div className="two-cols editor-top">
        <Card className={`option-card map-option ${hasShape ? 'selected' : ''}`}>
          <h3><MapPin size={22} /> Délimiter sur la carte</h3>
          <p className="muted">Entourez votre terrain au crayon, quelle que soit sa forme.</p>
          <button type="button" className="map-teaser" ref={teaserRef} onClick={openMap}>
            {hasShape ? (
              <svg className="teaser-shape" viewBox="0 0 100 60" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
                <polygon points={shapePoints(parcel.geometry)} />
              </svg>
            ) : <span className="teaser-poly" />}
            <span className="btn btn-light">
              {hasShape ? <><Pencil size={16} /> Modifier · {polygonAreaHa(parcel.geometry).toFixed(2)} ha</> : <>Ouvrir la carte <ArrowRight size={16} /></>}
            </span>
          </button>
        </Card>

        <Card className="option-card">
          <h3><FileText size={22} /> Importer un fichier</h3>
          <p className="muted">Rapport d'analyse de sol (PDF) ou limites de parcelle (GeoJSON).</p>
          <div className={`dropzone ${dragOver ? 'over' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true) }} onDragLeave={() => setDragOver(false)}
            onDrop={(e) => { e.preventDefault(); setDragOver(false); handleFiles(e.dataTransfer.files) }}>
            <UploadCloud size={30} />
            <p>Glisser-déposer votre fichier ici ou <button type="button" className="link" onClick={() => fileInput.current.click()}>parcourir</button></p>
            <input ref={fileInput} type="file" hidden accept=".pdf,.png,.jpg,.jpeg,.webp,.geojson,.json" onChange={(e) => handleFiles(e.target.files)} />
          </div>
          <small className="muted">{reading ? 'Lecture du rapport en cours…' : DATA_MODE === 'api'
            ? 'Formats acceptés : PDF, image, GeoJSON. Le pH du rapport de sol est lu automatiquement (clé Gemini requise côté serveur).'
            : 'Formats acceptés : PDF, GeoJSON. En mode démo, le fichier est seulement joint.'}</small>
          {fileError && <p className="error-text">{fileError}</p>}
          {parcel.documents?.length > 0 && (
            <ul className="file-list">
              {parcel.documents.map((d, i) => (
                <li key={`${d.name}-${i}`}><FileText size={16} /> {d.name}
                  <button type="button" className="icon-btn" aria-label="Retirer"
                    onClick={() => set({ documents: parcel.documents.filter((_, j) => j !== i) })}><X size={14} /></button>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Card>
        <h3>Informations de la parcelle</h3>
        <div className="form-grid">
          <label>Nom<input value={parcel.name} onChange={(e) => set({ name: e.target.value })} placeholder="Ex. Parcelle Nord" required /></label>
          <label>Culture actuelle<input value={parcel.crop || ''} onChange={(e) => set({ crop: e.target.value })} placeholder="Ex. Blé dur" /></label>
          <label>Zone agro-écologique
            <select value={parcel.zone || ''} onChange={(e) => set({ zone: e.target.value })}>
              <option value="">— Choisir —</option>
              {ZONES.map((z) => <option key={z}>{z}</option>)}
            </select>
          </label>
          <label>Irrigation
            <select value={parcel.irrigation} onChange={(e) => set({ irrigation: e.target.value })}>
              <option>Pluviale</option><option>Goutte-à-goutte (limitée)</option><option>Irrigation complète</option>
            </select>
          </label>
          <label>pH du sol (analyse)
            <input type="number" step="0.1" min="3" max="10" value={parcel.ph ?? ''} placeholder="Ex. 7,8"
              onChange={(e) => set({ ph: e.target.value === '' ? null : Number(e.target.value) })} />
          </label>
        </div>
      </Card>

      {error && <ErrorState message={error} />}
      <div className="center-actions">
        <button className="btn btn-primary btn-lg" disabled={saving}>{saving ? 'Enregistrement…' : 'Continuer'} <ArrowRight size={18} /></button>
      </div>
    </form>
  )
}
